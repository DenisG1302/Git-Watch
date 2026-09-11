import html
import json
import logging
import re
import sqlite3
import threading
import time
from urllib.parse import quote
from .clients import GitHub, InputError, RemoteError, Telegram, event_text, parse_repo, validate_repo
from .store import Store
from .telegram_repos import MAIN_KEYBOARD, RepositoryDialogue

log = logging.getLogger('gitwatch')


class Watcher:
    def __init__(self, directory):
        self.store = Store(directory)
        proxy_file = self.store.directory / 'telegram-proxy.json'
        proxies = json.loads(proxy_file.read_text(encoding='utf-8')) if proxy_file.exists() else {}
        if not isinstance(proxies, dict) or any(k not in ('http','https') or not isinstance(v,str) for k,v in proxies.items()):
            raise ValueError('Invalid telegram-proxy.json; expected an http/https proxy mapping')
        self.github = GitHub(self.store)
        self.telegram = Telegram(proxies)
        self.repo_dialogue = RepositoryDialogue(self)
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.tg_lock = threading.RLock()
        self.check_lock = threading.Lock()
        self.checking = set()
        self.threads = []
        self.started_at = time.time()
        self.last_prune = 0
        self.next_send = 0

    def start(self):
        if self.threads:
            return
        for name, method in [('github',self.poll_once), ('telegram',self.telegram_once), ('delivery',self.deliver_once)]:
            thread = threading.Thread(target=self._loop, args=(name,method), name='gitwatch-'+name, daemon=True)
            self.threads.append(thread)
            thread.start()

    def stop(self):
        self.stop_event.set()
        self.wake.set()

    def _loop(self, name, method):
        while not self.stop_event.is_set():
            try:
                method()
            except Exception as exc:
                # Requests exceptions may contain secret-bearing URLs; never log their text.
                log.error('%s worker failed: %s', name, type(exc).__name__)
                self.store.put_meta('worker_'+name, {'error':'Временная ошибка. Повторяем автоматически.', 'at':time.time()})
            if name == 'github':
                self.wake.wait(1)
                self.wake.clear()
            else:
                self.stop_event.wait(1)

    def snapshot(self):
        settings = self.store.settings()
        repos = self.store.repos()
        for repo in repos:
            repo['heads'] = json.loads(repo['heads'])
            repo['checking'] = repo['id'] in self.checking
            repo['enabled'] = bool(repo['enabled'])
        with self.store.transaction() as db:
            pending = db.execute("SELECT count(*) FROM events WHERE delivery='pending'").fetchone()[0]
            recent = db.execute('SELECT count(*) FROM events WHERE created>?', (time.time()-86400,)).fetchone()[0]
        tg_poll = self.store.meta('tg_poll', {})
        tg_send = self.store.meta('tg_send', {})
        errors = [h for h in (tg_poll,tg_send) if h.get('error')]
        error = max(errors, key=lambda h:h.get('at',0))['error'] if errors else ''
        return {
            'now':time.time(), 'started_at':self.started_at,
            'running':bool(self.threads) and all(t.is_alive() for t in self.threads),
            'repos':repos, 'events':self.store.events(),
            'stats':{'active':sum(r['enabled'] for r in repos),'events':recent,'pending':pending},
            'settings':{'revision':settings['revision'], 'github_configured':bool(settings['github_token']),
                'telegram':{'configured':bool(settings['telegram_token']), 'username':settings['username'],
                'bot_username':settings['bot_username'], 'connected':bool(settings['chat_id']),
                'proxy_enabled':bool(self.telegram.proxies), 'error':error}},
            'github':self.store.meta('github', {}),
        }

    def branch_choices(self, value):
        name = parse_repo(value)
        metadata = self.github.metadata(name)
        name = parse_repo(metadata['full_name'])
        default = metadata.get('default_branch') or ''
        heads = self.github.heads({'full_name':name, 'mode':'all'})
        if not isinstance(heads, dict) or any(not isinstance(branch, str) or not branch for branch in heads):
            raise RemoteError('GitHub вернул некорректный список веток. Обнови список.')
        branches = sorted(heads, key=lambda branch:(branch != default, branch.casefold(), branch))
        return {'full_name':name, 'default_branch':default, 'branches':branches}

    def add_repo(self, body):
        name, mode, branch, interval = validate_repo(body)
        with self.store.transaction() as db:
            if db.execute('SELECT 1 FROM repos WHERE full_name=?',(name,)).fetchone():
                raise InputError('Этот репозиторий уже добавлен. Измени его настройки в списке.')
            if db.execute('SELECT count(*) FROM repos').fetchone()[0] >= 100:
                raise InputError('Можно отслеживать до 100 репозиториев.')
        meta = self.github.metadata(name)
        canonical = parse_repo(meta['full_name'])
        if mode == 'branch':
            self.github.get('/repos/'+canonical+'/branches/'+quote(branch,safe=''))
        try:
            with self.store.transaction() as db:
                cursor = db.execute('INSERT INTO repos (full_name,url,description,mode,branch,interval_minutes) VALUES (?,?,?,?,?,?)', (canonical,'https://github.com/'+canonical,str(meta.get('description') or '')[:500],mode,branch,interval))
                repo_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise InputError('Этот репозиторий уже добавлен.') from None
        self.wake.set()
        return {'id':repo_id}

    def update_repo(self, repo_id, body):
        with self.store.transaction() as db:
            old = self.store.repo(repo_id, db)
            if not old:
                raise InputError('Репозиторий уже удалён.')
            if body.get('revision') != old['revision']:
                raise InputError('Настройки уже изменились. Обнови страницу и повтори.')
            _, mode, branch, interval = validate_repo({**old, **body, 'url':old['url']})
            enabled = body.get('enabled', bool(old['enabled']))
            if type(enabled) is not bool:
                raise InputError('Некорректное состояние мониторинга.')
            reset = mode != old['mode'] or branch != old['branch']
            db.execute('UPDATE repos SET mode=?,branch=?,interval_minutes=?,enabled=?,heads=?,initialized=?,next_check=?,last_error=?,revision=revision+1 WHERE id=?',
                (mode,branch,interval,int(enabled),'{}' if reset else old['heads'],0 if reset else old['initialized'],time.time(),'' if reset else old['last_error'],repo_id))
        self.wake.set()

    def remove_repo(self, repo_id):
        with self.store.transaction() as db:
            db.execute("UPDATE events SET delivery='skipped',error='Репозиторий удалён.' WHERE repo_id=? AND delivery='pending'", (repo_id,))
            db.execute('DELETE FROM repos WHERE id=?',(repo_id,))

    def request_check(self, repo_id=None):
        with self.store.transaction() as db:
            # A manual check never overrides a GitHub rate-limit cooldown.
            sql = 'UPDATE repos SET next_check=? WHERE enabled=1'
            args = [time.time()]
            if repo_id is not None:
                sql += ' AND id=?'
                args.append(repo_id)
            db.execute(sql, args)
        self.wake.set()

    def poll_once(self):
        now = time.time()
        if now-self.last_prune > 86400:
            self.store.prune()
            self.last_prune = now
        if self.store.meta('github',{}).get('retry_at',0) > now:
            return
        due = sorted((r for r in self.store.repos() if r['enabled'] and r['next_check'] <= now), key=lambda r:r['next_check'])
        if due:
            self.check_repo(due[0]['id'])

    def check_repo(self, repo_id):
        if not self.check_lock.acquire(blocking=False):
            return
        repo = self.store.repo(repo_id)
        try:
            if not repo or not repo['enabled']:
                return
            self.checking.add(repo_id)
            heads = self.github.heads(repo)
            if not isinstance(heads,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not re.fullmatch(r'[0-9a-f]{40,64}',v) for k,v in heads.items()):
                raise RemoteError('GitHub вернул некорректные данные веток. Повторим проверку.')
            old_heads = json.loads(repo['heads'])
            changes = []
            if repo['initialized']:
                for branch in sorted(set(old_heads) | set(heads)):
                    old, new = old_heads.get(branch,''), heads.get(branch,'')
                    if old == new:
                        continue
                    details = self.github.details(repo['full_name'],old,new) if new else {'summary':'','author':'','commit_count':None}
                    kind = 'branch_created' if not old else 'branch_deleted' if not new else details.get('kind','push')
                    url = repo['url']+'/compare/'+old+'...'+new if old and new else repo['url']+'/commit/'+new if new else repo['url']+'/branches'
                    changes.append({'branch':branch,'old_sha':old,'sha':new,'kind':kind,'url':url,**{k:details.get(k) for k in ('summary','author','commit_count')}})
            now = time.time()
            with self.store.transaction() as db:
                current = self.store.repo(repo_id, db)
                if not current or current['revision'] != repo['revision'] or not current['enabled']:
                    return
                settings = self.store.settings(db)
                delivery = 'pending' if settings['telegram_token'] and settings['username'] else 'disabled'
                for event in changes:
                    db.execute('INSERT INTO events (repo_id,full_name,branch,kind,old_sha,sha,summary,author,commit_count,url,created,delivery,generation) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (repo_id,repo['full_name'],event['branch'],event['kind'],event['old_sha'],event['sha'],event['summary'],event['author'],event['commit_count'],event['url'],now,delivery,settings['generation']))
                db.execute('UPDATE repos SET heads=?,initialized=1,last_checked=?,next_check=?,last_error=?,last_change=? WHERE id=?',
                    (json.dumps(heads),now,now+repo['interval_minutes']*60,'' if heads or repo['mode']=='all' else 'Ветка пока не существует. Продолжаем наблюдение.',now if changes else repo['last_change'],repo_id))
        except RemoteError as exc:
            with self.store.transaction() as db:
                db.execute('UPDATE repos SET last_checked=?,next_check=?,last_error=? WHERE id=? AND revision=?',
                    (time.time(),max(time.time()+repo['interval_minutes']*60,exc.retry_at),str(exc),repo_id,repo['revision']))
        except Exception as exc:
            log.error('Repository check failed: %s',type(exc).__name__)
            if repo:
                with self.store.transaction() as db:
                    db.execute('UPDATE repos SET next_check=?,last_error=? WHERE id=? AND revision=?',
                        (time.time()+repo['interval_minutes']*60,'Не удалось обработать ответ GitHub. Повторим проверку автоматически.',repo_id,repo['revision']))
        finally:
            self.checking.discard(repo_id)
            self.check_lock.release()

    def configure_telegram(self, body):
        username = body.get('username', '')
        if not isinstance(username,str) or not re.fullmatch(r'@?[a-zA-Z0-9_]{1,32}', username.strip()):
            raise InputError('Укажи @ник своего личного Telegram-аккаунта.')
        username = username.strip().lstrip('@').lower()
        with self.tg_lock:
            old = self.store.settings()
            if body.get('revision') != old['revision']:
                raise InputError('Подключения уже изменились. Открой настройки заново.')
            token = body.get('token') or old['telegram_token']
            if not isinstance(token,str) or not re.fullmatch(r'\d+:[A-Za-z0-9_-]{20,}',token.strip()):
                raise InputError('Укажи токен бота, полученный у @BotFather.')
            token = token.strip()
            bot = self.telegram.call(token,'getMe',{})
            hook = self.telegram.call(token,'getWebhookInfo',{})
            if hook.get('url'):
                raise InputError('У этого бота включён webhook другого приложения. Создай отдельного бота в @BotFather.')
            if not bot.get('is_bot') or not bot.get('username'):
                raise InputError('Telegram не подтвердил бота.')
            changed = token != old['telegram_token'] or username != old['username']
            with self.store.transaction() as db:
                current = self.store.settings(db)
                if current['revision'] != old['revision']:
                    raise InputError('Подключения уже изменились. Открой настройки заново.')
                current.update(telegram_token=token,username=username,bot_username=bot['username'],revision=current['revision']+1)
                if changed:
                    current.update(chat_id=0,binding_after=int(time.time()),offset=0,generation=current['generation']+1)
                    db.execute("UPDATE events SET delivery='skipped',error='Получатель Telegram изменён.' WHERE delivery='pending'")
                    db.execute("DELETE FROM meta WHERE key='telegram_add_repo'")
                self.store.save_settings(current,db)
            self.store.put_meta('tg_poll',{})
            self.store.put_meta('tg_send',{})

    def disconnect_telegram(self):
        with self.tg_lock, self.store.transaction() as db:
            current = self.store.settings(db)
            current.update(telegram_token='',username='',bot_username='',chat_id=0,offset=0,generation=current['generation']+1,revision=current['revision']+1)
            self.store.save_settings(current,db)
            db.execute("UPDATE events SET delivery='skipped',error='Telegram отключён.' WHERE delivery='pending'")
            db.execute("DELETE FROM meta WHERE key='telegram_add_repo'")
        self.store.put_meta('tg_poll',{})
        self.store.put_meta('tg_send',{})

    def configure_github(self, body):
        old = self.store.settings()
        if body.get('revision') != old['revision']:
            raise InputError('Подключения уже изменились. Открой настройки заново.')
        token = body.get('token')
        if not isinstance(token,str) or len(token)>300 or any(c.isspace() for c in token.strip()):
            raise InputError('Некорректный GitHub-токен.')
        token = token.strip()
        if token:
            # A replacement token must be testable even after the previous token hit its quota.
            self.store.put_meta('github',{})
            self.github.get('/user', token=token)
        with self.store.transaction() as db:
            current = self.store.settings(db)
            if current['revision'] != old['revision']:
                raise InputError('Подключения уже изменились. Открой настройки заново.')
            current.update(github_token=token,revision=current['revision']+1)
            self.store.save_settings(current,db)
        self.store.put_meta('github',{})
        self.request_check()

    def _send(self, settings, text, keyboard=False):
        delay = max(self.next_send,self.store.meta('tg_send',{}).get('retry_at',0))-time.time()
        if delay > 2:
            raise RemoteError('Telegram ограничил частоту сообщений. Отправка продолжится автоматически.',time.time()+delay,429)
        if delay > 0 and self.stop_event.wait(delay):
            return
        payload = {'chat_id':settings['chat_id'],'text':text,'parse_mode':'HTML','link_preview_options':{'is_disabled':True}}
        if keyboard:
            payload['reply_markup'] = {'keyboard':MAIN_KEYBOARD if keyboard is True else keyboard,'resize_keyboard':True}
        try:
            self.telegram.call(settings['telegram_token'],'sendMessage',payload)
        except RemoteError as exc:
            self.store.put_meta('tg_send',{'error':str(exc),'retry_at':exc.retry_at,'at':time.time()})
            raise
        finally:
            self.next_send = time.time()+1.1
        self.store.put_meta('tg_send',{'at':time.time()})

    def test_telegram(self):
        with self.tg_lock:
            current = self.store.settings()
            if not current['chat_id']:
                raise InputError('Сначала отправь боту /start со своего аккаунта.')
            self._send(current,'<b>Git Watch подключён</b>\nТестовое уведомление. Здесь будут появляться новые пуши и изменения веток.'+ ('\nСоединение через настроенный прокси.' if self.telegram.proxies else ''),keyboard=True)

    def telegram_once(self):
        settings = self.store.settings()
        health = self.store.meta('tg_poll',{})
        if not settings['telegram_token'] or not settings['username'] or health.get('retry_at',0)>time.time():
            return
        try:
            updates = self.telegram.call(settings['telegram_token'],'getUpdates',{'offset':settings['offset'],'timeout':20,'allowed_updates':['message']})
            for update in updates:
                with self.tg_lock:
                    current = self.store.settings()
                    if current['generation'] != settings['generation']:
                        return
                    try:
                        self.process_update(update,current)
                    finally:
                        with self.store.transaction() as db:
                            current = self.store.settings(db)
                            if current['generation'] == settings['generation']:
                                current['offset'] = max(current['offset'],update['update_id']+1)
                                self.store.save_settings(current,db)
            if self.store.settings()['generation'] == settings['generation']:
                self.store.put_meta('tg_poll',{'at':time.time()})
        except RemoteError as exc:
            if self.store.settings()['generation'] == settings['generation']:
                self.store.put_meta('tg_poll',{'error':str(exc),'at':time.time(),'retry_at':max(exc.retry_at,time.time()+(60 if exc.status==409 else 15))})

    def process_update(self, update, settings):
        message = update.get('message',{})
        user, chat = message.get('from',{}), message.get('chat',{})
        user_id = user.get('id')
        if type(user_id) is not int or user_id<=0 or user.get('is_bot') or chat.get('type')!='private' or chat.get('id')!=user_id:
            return False
        if str(user.get('username','')).lower() != settings['username']:
            return False
        if settings['chat_id'] and settings['chat_id'] != user_id:
            return False
        if message.get('date',0)<settings['binding_after']:
            return False
        text = str(message.get('text','')).strip()
        command = text.split()[0].split('@')[0].lower() if text else ''
        if not settings['chat_id']:
            if command != '/start':
                return False
            with self.store.transaction() as db:
                current = self.store.settings(db)
                if current['generation']!=settings['generation']:
                    return False
                current['chat_id'] = user_id
                self.store.save_settings(current,db)
                settings = current
        if command == '/start':
            self.repo_dialogue.clear()
        if command in ('/start','/help'):
            self._send(settings,'<b>Git Watch</b>\nЛичный чат привязан. Доступ разрешён только тебе.\n\n/add — добавить репозиторий\n/status — состояние репозиториев\n/check — проверить сейчас\n/repos — список репозиториев\n/cancel — отменить добавление\n\nМожно просто прислать ссылку на GitHub. Незавершённое добавление продолжается командой /add.',keyboard=self.repo_dialogue.keyboard(settings))
        elif self.repo_dialogue.handle(update,settings,text,command):
            return True
        elif command == '/check' or text == '↻ Проверить':
            self.request_check()
            self._send(settings,'Проверка активных репозиториев запрошена. Новые изменения придут отдельными сообщениями.',keyboard=self.repo_dialogue.keyboard(settings))
        elif command in ('/status','/repos') or text == '📊 Статус':
            repos = self.store.repos()
            lines = ['<b>Git Watch · Статус</b>',f'Активны: {sum(bool(r["enabled"]) for r in repos)} из {len(repos)}','']
            for repo in repos[:20]:
                state = 'Пауза' if not repo['enabled'] else 'Ошибка проверки' if repo['last_error'] else 'Наблюдение' if repo['initialized'] else 'Первый опрос'
                lines.append(html.escape(repo['full_name'])+' · '+state+' · '+str(repo['interval_minutes'])+' мин')
            if len(repos)>20:
                lines.append('Остальные репозитории доступны на сайте.')
            if not repos:
                lines.append('Нажми «➕ Добавить репозиторий» или отправь /add, чтобы начать наблюдение.')
            self._send(settings,'\n'.join(lines),keyboard=self.repo_dialogue.keyboard(settings))
        elif text:
            self._send(settings,'Доступные команды: /add, /status, /repos, /check, /cancel. Для продолжения добавления отправь /add.',keyboard=self.repo_dialogue.keyboard(settings))
        return True

    def deliver_once(self):
        with self.tg_lock:
            settings = self.store.settings()
            if not settings['telegram_token'] or not settings['chat_id']:
                return
            if self.store.meta('tg_send',{}).get('retry_at',0)>time.time():
                return
            with self.store.transaction() as db:
                row = db.execute("SELECT * FROM events WHERE delivery='pending' AND next_attempt<=? ORDER BY id LIMIT 1",(time.time(),)).fetchone()
                if not row:
                    return
                event = dict(row)
                if event['generation'] != settings['generation']:
                    db.execute("UPDATE events SET delivery='skipped',error='Получатель Telegram изменён.' WHERE id=?",(event['id'],))
                    return
            try:
                self._send(settings,event_text(event))
            except RemoteError as exc:
                with self.store.transaction() as db:
                    retry = max(exc.retry_at,time.time()+min(3600,15*2**min(event['attempts'],8)))
                    db.execute('UPDATE events SET attempts=attempts+1,next_attempt=?,error=? WHERE id=?',(retry,str(exc),event['id']))
                return
            with self.store.transaction() as db:
                db.execute("UPDATE events SET delivery='sent',error='' WHERE id=?",(event['id'],))
