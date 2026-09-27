import tempfile
import time
import unittest
from unittest.mock import Mock

from gitwatch.clients import RemoteError
from gitwatch.service import Watcher
from gitwatch.web import create_app


class DashboardLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.watcher = Watcher(self.temp.name)
        self.watcher.github = Mock()
        self.watcher.github.metadata.return_value = {
            'full_name': 'owner/project', 'description': 'Описание проекта', 'default_branch': 'main',
        }
        self.client = create_app(watcher=self.watcher).test_client()

    def test_validation_uses_requested_language_and_preserves_default(self):
        for language, expected, code in [
            ('en-US,en;q=0.9', 'Enter the repository URL: https://github.com/owner/repository.', 'en'),
            ('en;q=0.5,ru;q=0.9', 'Нужна ссылка на сам репозиторий: https://github.com/owner/repository.', 'ru'),
            ('', 'Нужна ссылка на сам репозиторий: https://github.com/owner/repository.', 'ru'),
        ]:
            with self.subTest(language=language):
                response = self.client.post('/api/repos', json={'url': ''}, headers={
                    'X-GitWatch': '1', 'Accept-Language': language,
                })
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['error'], expected)
                self.assertEqual(response.headers['Content-Language'], code)
                self.assertIn('Accept-Language', response.headers['Vary'])

    def test_security_rejections_are_localized_without_relaxing_guards(self):
        response = self.client.post('/api/check', json={}, headers={'Accept-Language': 'en'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json['error'], 'Request rejected. Open the dashboard directly and try again.')
        self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
        self.assertNotIn('unsafe-eval', response.headers['Content-Security-Policy'])

    def test_remote_errors_keep_retry_metadata(self):
        self.watcher.github.metadata.side_effect = RemoteError(
            'Нет соединения с GitHub. Повторим проверку автоматически.', retry_at=12345,
        )
        response = self.client.post('/api/repos/branches', json={'url': 'owner/project'}, headers={
            'X-GitWatch': '1', 'Accept-Language': 'en',
        })
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json['error'], 'Could not connect to GitHub. Checks will retry automatically.')
        self.assertEqual(response.json['retry_at'], 12345)

    def test_snapshot_translates_errors_without_changing_storage_or_user_content(self):
        repo_id = self.watcher.add_repo({'url': 'owner/project', 'mode': 'all', 'interval_minutes': 5})['id']
        repo_error = 'Ветка пока не существует. Продолжаем наблюдение.'
        event_error = 'Telegram отключён.'
        bot_error = 'Нет ответа от Telegram. Повторим автоматически.'
        with self.watcher.store.transaction() as db:
            db.execute('UPDATE repos SET last_error=? WHERE id=?', (repo_error, repo_id))
            db.execute('INSERT INTO events (repo_id,full_name,branch,kind,summary,author,url,created,delivery,generation,error) '
                       'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (repo_id, 'owner/project', 'ветка', 'push', 'Изменения проекта', 'Автор',
                        'https://github.com/owner/project', time.time(), 'skipped', 0, event_error))
        self.watcher.store.put_meta('tg_poll', {'error': bot_error, 'at': time.time()})
        english = self.client.get('/api/state', headers={'Accept-Language': 'en'}).json
        self.assertEqual(english['repos'][0]['last_error'], 'The branch does not exist yet. Monitoring will continue.')
        self.assertEqual(english['events'][0]['error'], 'Telegram disconnected.')
        self.assertEqual(english['settings']['telegram']['error'], 'Telegram did not respond. The request will retry automatically.')
        self.assertEqual(english['repos'][0]['description'], 'Описание проекта')
        self.assertEqual(english['events'][0]['branch'], 'ветка')
        self.assertEqual(english['events'][0]['summary'], 'Изменения проекта')
        self.assertEqual(english['events'][0]['author'], 'Автор')
        russian = self.client.get('/api/state', headers={'Accept-Language': 'ru'}).json
        self.assertEqual(russian['repos'][0]['last_error'], repo_error)
        self.assertEqual(russian['events'][0]['error'], event_error)
        self.assertEqual(russian['settings']['telegram']['error'], bot_error)
        self.assertEqual(self.watcher.store.repo(repo_id)['last_error'], repo_error)
        self.assertEqual(self.watcher.store.meta('tg_poll')['error'], bot_error)


if __name__ == '__main__':
    unittest.main()
