import html
import re
import time
from urllib.parse import quote, urlsplit
import requests


class InputError(ValueError):
    pass


class RemoteError(Exception):
    def __init__(self, message, retry_at=0, status=0):
        super().__init__(message)
        self.retry_at = retry_at
        self.status = status


def parse_repo(value):
    if not isinstance(value, str) or len(value) > 300:
        raise InputError('Укажи ссылку вида https://github.com/owner/repository.')
    value = value.strip().rstrip('/')
    if value.startswith('https://'):
        parts = urlsplit(value)
        if parts.netloc.lower() != 'github.com' or parts.query or parts.fragment:
            raise InputError('Поддерживаются ссылки на репозитории github.com без дополнительных параметров.')
        value = parts.path.lstrip('/')
    elif value.startswith('github.com/'):
        value = value[len('github.com/'):]
    if value.endswith('.git'):
        value = value[:-4]
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', value) or value.split('/')[-1] in ('.', '..'):
        raise InputError('Нужна ссылка на сам репозиторий: https://github.com/owner/repository.')
    return value


def validate_repo(body):
    name = parse_repo(body.get('url', ''))
    interval = body.get('interval_minutes', 5)
    if type(interval) is not int or not 1 <= interval <= 1440:
        raise InputError('Интервал должен быть целым числом от 1 до 1440 минут.')
    mode = body.get('mode', 'all')
    branch = body.get('branch', '')
    if mode not in ('all', 'default', 'branch'):
        raise InputError('Выбери все ветки, основную или указанную ветку.')
    if not isinstance(branch, str):
        raise InputError('Укажи имя ветки.')
    branch = branch.strip() if mode == 'branch' else ''
    if mode == 'branch' and (not branch or len(branch) > 200 or any(ord(c) < 32 or c in ' ~^:?*[\\' for c in branch) or '..' in branch or '@{' in branch or branch.startswith('/') or branch.endswith(('/', '.', '.lock'))):
        raise InputError('Укажи корректное имя ветки, например main или feature/example.')
    return name, mode, branch, interval


class GitHub:
    def __init__(self, store):
        self.store = store

    def get(self, path, token=None):
        rate = self.store.meta('github', {})
        if rate.get('retry_at', 0) > time.time():
            raise RemoteError('GitHub ограничил частоту запросов. Проверки продолжатся автоматически.', rate['retry_at'], 429)
        if token is None:
            token = self.store.settings()['github_token']
        headers = {'Accept':'application/vnd.github+json', 'User-Agent':'Git-Watch/1.0', 'X-GitHub-Api-Version':'2026-03-10'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        try:
            r = requests.get('https://api.github.com' + path, headers=headers, timeout=(8, 25))
        except requests.RequestException:
            raise RemoteError('Нет соединения с GitHub. Повторим проверку автоматически.') from None
        try:
            rate = {'remaining':int(r.headers.get('X-RateLimit-Remaining', '-1')), 'limit':int(r.headers.get('X-RateLimit-Limit','0')), 'reset':int(r.headers.get('X-RateLimit-Reset','0')), 'retry_at':0}
            if rate['remaining'] == 0:
                rate['retry_at'] = max(time.time()+30, rate['reset']+2)
            if r.status_code in (403, 429):
                rate['retry_at'] = max(rate['retry_at'], time.time()+max(60, int(r.headers.get('Retry-After','60'))))
            self.store.put_meta('github', rate)
        except (ValueError, TypeError):
            rate = {}
        if r.status_code == 401:
            raise RemoteError('GitHub не принял токен. Обнови его в настройках.', status=401)
        if r.status_code == 404:
            raise RemoteError('Репозиторий или ветка не найдены. Для приватного репозитория проверь доступ токена.', status=404)
        if r.status_code in (403, 429):
            raise RemoteError('GitHub ограничил запросы или доступ. Проверь разрешения токена; опрос возобновится автоматически.', rate.get('retry_at',time.time()+60), r.status_code)
        if r.status_code >= 400:
            raise RemoteError('GitHub временно не вернул данные. Повторим проверку.', status=r.status_code)
        try:
            return r.json()
        except ValueError:
            raise RemoteError('GitHub вернул некорректный ответ. Повторим проверку.') from None

    def metadata(self, name):
        return self.get('/repos/' + name)

    def heads(self, repo):
        path = '/repos/' + repo['full_name']
        if repo['mode'] != 'all':
            branch = repo['branch'] if repo['mode'] == 'branch' else self.metadata(repo['full_name'])['default_branch']
            try:
                row = self.get(path + '/branches/' + quote(branch, safe=''))
            except RemoteError as exc:
                if exc.status == 404:
                    # Distinguish a deleted branch from lost repository access.
                    self.metadata(repo['full_name'])
                    return {}
                raise
            return {row['name']: row['commit']['sha']}
        result = {}
        for page in range(1, 102):
            rows = self.get(path + '/branches?per_page=100&page=' + str(page))
            if not isinstance(rows, list):
                raise RemoteError('GitHub вернул некорректный список веток.')
            for row in rows:
                result[row['name']] = row['commit']['sha']
            if len(rows) < 100:
                return result
        raise RemoteError('Слишком много веток. Выбери одну ветку для этого репозитория.')

    def details(self, name, old, new):
        result = {'summary':'', 'author':'', 'commit_count':None, 'kind':'push'}
        try:
            data = self.get('/repos/' + name + '/commits/' + new)
            result['summary'] = data['commit']['message'].split('\n')[0][:450]
            result['author'] = (data.get('author') or {}).get('login') or data['commit']['author'].get('name','')
        except (RemoteError, KeyError, TypeError):
            return result
        if old:
            try:
                comparison = self.get('/repos/' + name + '/compare/' + old + '...' + new + '?per_page=1')
                result['commit_count'] = comparison.get('total_commits')
                if comparison.get('status') in ('diverged', 'behind'):
                    result['kind'] = 'rewrite'
            except RemoteError:
                pass
        return result


class Telegram:
    def __init__(self, proxies=None):
        self.proxies = proxies or {}

    def call(self, token, method, body):
        try:
            response = requests.post('https://api.telegram.org/bot'+token+'/'+method, json=body, proxies=self.proxies, timeout=(8, 35 if method == 'getUpdates' else 20))
            data = response.json()
        except (requests.RequestException, ValueError):
            raise RemoteError('Нет ответа от Telegram. Повторим автоматически.') from None
        if not data.get('ok'):
            status = data.get('error_code', response.status_code)
            messages = {401:'Telegram не принял токен бота.', 403:'Бот заблокирован. Открой чат и нажми «Запустить».', 409:'Токен бота уже используется другим приложением. Создай отдельного бота.', 429:'Telegram ограничил частоту сообщений. Отправка продолжится автоматически.'}
            delay = data.get('parameters',{}).get('retry_after', 0)
            raise RemoteError(messages.get(status,'Telegram не смог выполнить запрос. Проверь подключение.'), time.time()+delay if delay else 0, status)
        return data['result']


def event_text(event):
    esc = lambda s: html.escape(str(s), quote=True)
    titles = {'push':'Новый пуш', 'rewrite':'История ветки изменена', 'branch_created':'Новая ветка', 'branch_deleted':'Ветка удалена'}
    lines = ['<b>'+titles.get(event['kind'],'Изменения в репозитории')+'</b>', esc(event['full_name']), 'Ветка: <code>'+esc(event['branch'])+'</code>']
    if event.get('commit_count') is not None:
        lines.append('Новых коммитов: '+str(event['commit_count']))
    if event.get('summary'):
        lines.append('\n'+esc(event['summary']))
    if event.get('author'):
        lines.append('Автор: '+esc(event['author'][:160]))
    if event.get('sha'):
        lines.append('Коммит: <code>'+esc(event['sha'][:8])+'</code>')
    lines.append('\n<a href="'+esc(event['url'])+'">Открыть изменения на GitHub →</a>')
    return '\n'.join(lines)
