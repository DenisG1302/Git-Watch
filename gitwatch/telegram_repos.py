"""Repository setup in the already-authorized owner's private Telegram chat."""
import html
import re
import time
from urllib.parse import quote

from .clients import InputError, RemoteError, parse_repo, validate_repo

MAIN_KEYBOARD = [['➕ Добавить репозиторий'], ['📊 Статус', '↻ Проверить']]
MODE_KEYBOARD = [['Все ветки', 'Основная ветка'], ['Выбрать ветку'], ['Отмена']]
INTERVAL_KEYBOARD = [['1 мин', '5 мин', '15 мин'], ['30 мин', '60 мин'], ['Отмена']]
FLOW_KEY = 'telegram_add_repo'
FLOW_TTL = 30 * 60
BRANCH_PAGE_SIZE = 8
BRANCH_PREFIX = '⑂ '


class RepositoryDialogue:
    def __init__(self, watcher):
        self.w = watcher

    def clear(self):
        self.w.store.put_meta(FLOW_KEY, {})

    def load(self, settings):
        flow = self.w.store.meta(FLOW_KEY, {})
        if (flow.get('generation') != settings['generation']
                or flow.get('chat_id') != settings['chat_id']
                or time.time() - flow.get('updated_at', 0) > FLOW_TTL):
            return {}
        return flow

    def save(self, flow):
        flow['updated_at'] = time.time()
        self.w.store.put_meta(FLOW_KEY, flow)

    def keyboard(self, settings):
        flow = self.load(settings)
        stage = flow.get('stage')
        if stage == 'mode':
            return MODE_KEYBOARD
        if stage == 'interval':
            return INTERVAL_KEYBOARD
        if stage == 'branch':
            branches = flow.get('branches', [])
            page = flow.get('branch_page', 0)
            rows = [[BRANCH_PREFIX + branch] for branch in branches[page*BRANCH_PAGE_SIZE:(page+1)*BRANCH_PAGE_SIZE]]
            navigation = []
            if page > 0:
                navigation.append('‹ Назад')
            if (page+1)*BRANCH_PAGE_SIZE < len(branches):
                navigation.append('Далее ›')
            if navigation:
                rows.append(navigation)
            return rows + [['↻ Обновить ветки'], ['← К выбору режима', 'Отмена']]
        if stage == 'url':
            return [['Отмена']]
        return MAIN_KEYBOARD

    def fetch_branches(self, flow):
        choices = self.w.branch_choices(flow['url'])
        flow.update(branches=choices['branches'], default_branch=choices['default_branch'], branch_page=0)
        self.save(flow)

    def prompt(self, settings, flow, error=''):
        if flow['stage'] == 'branch' and 'branches' not in flow and not error:
            try:
                self.fetch_branches(flow)
            except (InputError, RemoteError) as exc:
                error = str(exc)
        name = html.escape(flow.get('full_name', ''))
        branches = flow.get('branches', [])
        if branches:
            pages = (len(branches)+BRANCH_PAGE_SIZE-1)//BRANCH_PAGE_SIZE
            branch_prompt = 'Выбери ветку кнопкой ниже.'
            if flow.get('default_branch'):
                branch_prompt += '\nОсновная: <code>' + html.escape(flow['default_branch']) + '</code>.'
            if pages > 1:
                branch_prompt += f'\nСтраница {flow.get("branch_page",0)+1} из {pages}.'
        elif 'branches' in flow:
            branch_prompt = 'В репозитории пока нет веток. Можно обновить список или вернуться и выбрать «Все ветки».'
        else:
            branch_prompt = 'Список веток пока недоступен. Нажми «↻ Обновить ветки», чтобы повторить загрузку.'
        messages = {
            'url': '<b>Добавить репозиторий</b>\nПришли ссылку на GitHub или <code>owner/repository</code>.',
            'mode': f'<b>{name}</b>\nКакие ветки проверять?',
            'branch': f'<b>{name}</b>\n{branch_prompt}',
            'interval': f'<b>{name}</b>\nКак часто проверять? Выбери интервал или пришли целое число минут от 1 до 1440.',
        }
        text = (html.escape(error) + '\n\n' if error else '') + messages[flow['stage']]
        text += '\n\n/cancel — отменить добавление'
        self.w._send(settings, text, keyboard=self.keyboard(settings))

    def accept_url(self, flow, value):
        name = parse_repo(value)
        existing = {repo['full_name'].lower() for repo in self.w.store.repos()}
        if name.lower() in existing:
            raise InputError('Этот репозиторий уже добавлен. Его настройки доступны на сайте.')
        metadata = self.w.github.metadata(name)
        name = parse_repo(metadata['full_name'])
        if name.lower() in existing:
            raise InputError('Этот репозиторий уже добавлен. Его настройки доступны на сайте.')
        flow.update(full_name=name, url='https://github.com/' + name, stage='mode')
        self.save(flow)

    def handle(self, update, settings, text, command):
        """Called only after the username, numeric ID and private-chat checks."""
        flow = self.load(settings)
        if flow.get('stage') == 'done' and update.get('update_id') == flow.get('completed_update'):
            return True
        if command == '/cancel' or text == 'Отмена':
            self.clear()
            self.w._send(settings, 'Добавление отменено.', keyboard=True)
            return True
        start = command == '/add' or text == '➕ Добавить репозиторий'
        argument = text.split(maxsplit=1)[1].strip() if command == '/add' and len(text.split(maxsplit=1)) == 2 else ''
        # A pasted link or owner/repository starts the same guided setup.
        if not start and (not flow or flow.get('stage') == 'done'):
            try:
                parse_repo(text)
            except InputError:
                return False
            start, argument = True, text
        if start:
            if argument or not flow or flow.get('stage') == 'done':
                flow = {'stage':'url', 'generation':settings['generation'], 'chat_id':settings['chat_id']}
                self.save(flow)
                if argument:
                    try:
                        self.accept_url(flow, argument)
                    except (InputError, RemoteError) as exc:
                        self.prompt(settings, flow, str(exc))
                        return True
            self.prompt(settings, flow)
            return True
        if not flow or flow.get('stage') == 'done':
            return False
        # Other bot commands keep their normal behavior without becoming form input.
        if text.startswith('/') or text in ('📊 Статус', '↻ Проверить'):
            return False
        completed_reply = None
        try:
            if flow['stage'] == 'url':
                self.accept_url(flow, text)
            elif flow['stage'] == 'mode':
                modes = {'все ветки':'all', 'все':'all', 'all':'all',
                         'основная ветка':'default', 'основная':'default', 'default':'default',
                         'выбрать ветку':'branch', 'указать ветку':'branch', 'branch':'branch'}
                mode = modes.get(text.lower())
                if not mode:
                    raise InputError('Выбери «Все ветки», «Основная ветка» или «Выбрать ветку».')
                flow.update(mode=mode, branch='', stage='branch' if mode == 'branch' else 'interval')
                flow.pop('branches', None)
                self.save(flow)
            elif flow['stage'] == 'branch':
                if text == '← К выбору режима':
                    flow['stage'] = 'mode'
                elif text == '↻ Обновить ветки':
                    self.fetch_branches(flow)
                elif text in ('‹ Назад', 'Далее ›'):
                    last_page = max(0, (len(flow.get('branches', []))-1)//BRANCH_PAGE_SIZE)
                    flow['branch_page'] = max(0, min(last_page, flow.get('branch_page', 0)+(1 if text == 'Далее ›' else -1)))
                else:
                    if 'branches' not in flow:
                        self.fetch_branches(flow)
                    branch = text[len(BRANCH_PREFIX):] if text.startswith(BRANCH_PREFIX) else text
                    if branch not in flow['branches']:
                        raise InputError('Выбери ветку из списка ниже. Если она появилась недавно, нажми «↻ Обновить ветки».')
                    _, _, branch, _ = validate_repo({**flow, 'branch':branch})
                    self.w.github.get('/repos/' + flow['full_name'] + '/branches/' + quote(branch, safe=''))
                    flow.update(branch=branch, stage='interval')
                self.save(flow)
            elif flow['stage'] == 'interval':
                match = re.fullmatch(r'([0-9]{1,4})(?:\s*мин(?:\.|ут(?:а|ы)?)?)?', text.lower())
                if not match or not 1 <= int(match[1]) <= 1440:
                    raise InputError('Пришли целое число минут от 1 до 1440, например 5, или выбери кнопку.')
                minutes = int(match[1])
                result = self.w.add_repo({'url':flow['url'], 'mode':flow['mode'],
                                          'branch':flow.get('branch', ''), 'interval_minutes':minutes})
                repo = self.w.store.repo(result['id'])
                flow.update(stage='done', completed_update=update.get('update_id'), repo_id=result['id'])
                self.save(flow)
                mode = {'all':'Все ветки', 'default':'Основная ветка', 'branch':repo['branch']}[repo['mode']]
                completed_reply = ('<b>Репозиторий добавлен</b>\n' + html.escape(repo['full_name'])
                    + '\nВетки: ' + html.escape(mode) + f'\nИнтервал: {minutes} мин'
                    + '\n\nУже доступен на сайте. Первый опрос запомнит текущее состояние; затем начнут приходить новые изменения.')
        except (InputError, RemoteError) as exc:
            # Keep the current step so an invalid value or temporary outage can be retried.
            self.prompt(settings, flow, str(exc))
            return True
        if completed_reply is not None:
            # Repository creation is complete even if Telegram loses the receipt.
            self.w._send(settings, completed_reply, keyboard=True)
            return True
        self.prompt(settings, flow)
        return True
