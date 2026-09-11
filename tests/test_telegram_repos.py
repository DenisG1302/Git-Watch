import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from gitwatch.clients import RemoteError
from gitwatch.service import Watcher
from gitwatch.telegram_repos import FLOW_KEY, FLOW_TTL, MAIN_KEYBOARD, MODE_KEYBOARD
from gitwatch.web import create_app


class TelegramRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.w = Watcher(self.temp.name)
        self.mock_external(self.w)
        self.configure(telegram_token='test-token', username='owner', chat_id=123)
        self.update_id = 0

    def tearDown(self):
        self.temp.cleanup()

    def mock_external(self, watcher):
        watcher.github = Mock()
        watcher.github.metadata.side_effect = lambda name: {'full_name':name, 'description':''}
        watcher._send = Mock()

    def configure(self, **changes):
        with self.w.store.transaction() as db:
            settings = self.w.store.settings(db)
            settings.update(changes)
            self.w.store.save_settings(settings, db)

    def packet(self, text, **overrides):
        self.update_id += 1
        message = {'date':int(time.time()), 'from':{'id':123, 'username':'owner'},
                   'chat':{'id':123, 'type':'private'}, 'text':text}
        message.update(overrides)
        return {'update_id':self.update_id, 'message':message}

    def send(self, text, **overrides):
        return self.w.process_update(self.packet(text, **overrides), self.w.store.settings())

    def flow(self):
        return self.w.repo_dialogue.load(self.w.store.settings())

    def test_guided_add_shares_web_state_and_keyboard(self):
        self.send('/start')
        self.assertIn(['➕ Добавить репозиторий'], self.w._send.call_args.kwargs['keyboard'])
        self.send('➕ Добавить репозиторий')
        self.assertEqual(self.flow()['stage'], 'url')
        self.send('https://github.com/owner/project')
        self.assertEqual(self.w._send.call_args.kwargs['keyboard'], MODE_KEYBOARD)
        self.send('Все ветки')
        self.assertEqual(self.w.store.repos(), [])
        self.send('5 мин')
        client = create_app(watcher=self.w).test_client()
        repo = client.get('/api/state').json['repos'][0]
        self.assertEqual((repo['full_name'], repo['mode'], repo['interval_minutes']), ('owner/project','all',5))
        self.assertFalse(repo['initialized'])
        self.assertIn('Репозиторий добавлен', self.w._send.call_args.args[1])
        self.w.telegram = Mock(proxies={})
        self.w.telegram.call.return_value = {}
        Watcher._send(self.w, self.w.store.settings(), 'Test keyboard', keyboard=True)
        self.assertEqual(self.w.telegram.call.call_args.args[2]['reply_markup']['keyboard'], MAIN_KEYBOARD)

    def test_shortcuts_and_branch_with_slash(self):
        for text in ('/add https://github.com/owner/project', '/add@WatchBot owner/project',
                     'https://github.com/owner/project.git', 'owner/project'):
            with self.subTest(text=text):
                self.send(text)
                self.assertEqual(self.flow()['stage'], 'mode')
                self.send('/cancel')
        self.send('/add owner/project')
        self.send('Указать ветку')
        self.send('feature/my-branch')
        self.w.github.get.assert_called_with('/repos/owner/project/branches/feature%2Fmy-branch')
        self.send('60')
        repo = self.w.store.repos()[0]
        self.assertEqual((repo['mode'], repo['branch'], repo['interval_minutes']), ('branch','feature/my-branch',60))

    def test_bad_inputs_can_be_corrected_without_creating_repositories(self):
        self.send('/add')
        self.send('https://evil.example/owner/project')
        self.w.github.metadata.assert_not_called()
        self.assertEqual(self.flow()['stage'], 'url')
        self.send('owner/project')
        self.send('wrong-mode')
        self.assertEqual(self.flow()['stage'], 'mode')
        self.send('Указать ветку')
        self.send('../secret')
        self.w.github.get.assert_not_called()
        self.assertEqual(self.flow()['stage'], 'branch')
        self.w.github.get.side_effect = RemoteError('Branch not found', status=404)
        self.send('missing-branch')
        self.assertIn('Branch not found', self.w._send.call_args.args[1])
        self.assertEqual(self.flow()['stage'], 'branch')
        self.w.github.get.side_effect = None
        self.send('main')
        for text in ('0', '1441', '-1', '1.5', 'abc', '9'*100):
            self.send(text)
            self.assertEqual(self.flow()['stage'], 'interval')
            self.assertEqual(self.w.store.repos(), [])
        self.send('1440')
        self.assertEqual(self.w.store.repos()[0]['interval_minutes'], 1440)

    def test_api_failures_and_duplicate_from_web_are_reported(self):
        self.w.github.metadata.side_effect = RemoteError('GitHub unavailable')
        self.send('/add owner/project')
        self.assertEqual(self.flow()['stage'], 'url')
        self.assertIn('GitHub unavailable', self.w._send.call_args.args[1])
        self.w.github.metadata.side_effect = lambda name: {'full_name':name}
        self.send('owner/project')
        self.send('Основная ветка')
        self.w.github.metadata.side_effect = RemoteError('No access', status=404)
        self.send('5')
        self.assertEqual(self.flow()['stage'], 'interval')
        self.assertEqual(self.w.store.repos(), [])
        self.w.github.metadata.side_effect = lambda name: {'full_name':name}
        self.w.add_repo({'url':'owner/project'})
        self.send('5')
        self.assertEqual(len(self.w.store.repos()), 1)
        self.assertIn('уже добавлен', self.w._send.call_args.args[1])
        self.send('/cancel')
        self.send('/add owner/project')
        self.assertIn('уже добавлен', self.w._send.call_args.args[1])

    def test_unauthorized_messages_cannot_change_a_dialogue(self):
        self.send('/add owner/project')
        flow = self.flow()
        self.w._send.reset_mock()
        self.w.github.reset_mock()
        for overrides in ({'from':{'id':456,'username':'owner'},'chat':{'id':456,'type':'private'}},
                          {'from':{'id':123,'username':'outsider'}},
                          {'chat':{'id':-123,'type':'group'}},
                          {'from':{'id':123,'username':'owner','is_bot':True}}):
            self.assertFalse(self.send('/add attacker/project', **overrides))
            self.assertEqual(self.flow(), flow)
        self.w._send.assert_not_called()
        self.w.github.metadata.assert_not_called()
        self.assertEqual(self.w.store.repos(), [])
        self.configure(chat_id=0)
        self.assertFalse(self.send('/add owner/project'))

    def test_restart_resume_commands_cancel_and_expiry(self):
        self.send('/add owner/project')
        self.send('/status')
        self.assertEqual(self.flow()['stage'], 'mode')
        restarted = Watcher(self.temp.name)
        self.mock_external(restarted)
        self.w = restarted
        self.send('/add')
        self.assertEqual(self.w._send.call_args.kwargs['keyboard'], MODE_KEYBOARD)
        self.send('Основная ветка')
        self.send('/repos')
        self.assertEqual(self.flow()['stage'], 'interval')
        self.send('15 мин')
        self.assertEqual(self.w.store.repos()[0]['mode'], 'default')
        self.send('/add owner/next')
        self.send('Отмена')
        self.assertFalse(self.flow())
        self.send('/add owner/next')
        self.send('/start')
        self.assertFalse(self.flow())
        self.send('/add owner/next')
        expired_at = self.flow()['updated_at'] + FLOW_TTL + 1
        with patch('gitwatch.telegram_repos.time.time', return_value=expired_at):
            self.assertFalse(self.flow())
        self.configure(generation=1)
        self.assertFalse(self.flow())
        self.send('/add')
        self.assertEqual(self.flow()['stage'], 'url')

    def test_lost_receipt_and_replayed_update_do_not_duplicate_creation(self):
        self.send('/add owner/project')
        self.send('Все ветки')
        update = self.packet('5')
        self.w._send.side_effect = RemoteError('Telegram unavailable')
        with self.assertRaises(RemoteError):
            self.w.process_update(update, self.w.store.settings())
        self.assertEqual(len(self.w.store.repos()), 1)
        self.assertEqual(self.flow()['stage'], 'done')
        self.w.github.reset_mock()
        self.w._send.side_effect = None
        self.w.process_update(update, self.w.store.settings())
        self.assertEqual(len(self.w.store.repos()), 1)
        self.w.github.metadata.assert_not_called()

    def test_poll_batch_advances_offsets_and_disconnect_discards_draft(self):
        self.w.telegram = Mock(proxies={})
        updates = [self.packet('/add owner/project'), self.packet('Основная ветка'), self.packet('30 мин')]
        self.w.telegram.call.return_value = updates
        self.w.telegram_once()
        self.assertEqual(self.w.store.settings()['offset'], updates[-1]['update_id']+1)
        self.assertEqual(self.w.store.repos()[0]['interval_minutes'], 30)
        self.send('/add owner/next')
        self.w.disconnect_telegram()
        self.assertEqual(self.w.store.meta(FLOW_KEY, {}), {})


if __name__ == '__main__':
    unittest.main()
