import tempfile
import time
import unittest
from unittest.mock import Mock

from gitwatch.clients import RemoteError
from gitwatch.service import Watcher
from gitwatch.telegram_repos import BRANCH_PAGE_SIZE, BRANCH_PREFIX, FLOW_KEY
from gitwatch.web import create_app


class BranchChoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.w = Watcher(self.temp.name)
        self.w.github = Mock()
        self.w.github.metadata.return_value = {'full_name':'owner/project', 'default_branch':'main'}
        self.w.github.heads.return_value = {'z-release':'a'*40, 'main':'b'*40, 'feature/sub':'c'*40}
        self.w._send = Mock()
        with self.w.store.transaction() as db:
            settings = self.w.store.settings(db)
            settings.update(username='owner', chat_id=123, telegram_token='secret')
            self.w.store.save_settings(settings, db)
        self.update_id = 0

    def tearDown(self):
        self.temp.cleanup()

    def send(self, text):
        self.update_id += 1
        self.w.process_update({'update_id':self.update_id, 'message':{
            'date':int(time.time()), 'text':text, 'from':{'id':123,'username':'owner'},
            'chat':{'id':123,'type':'private'}}}, self.w.store.settings())

    def buttons(self):
        return [text for row in self.w._send.call_args.kwargs['keyboard'] for text in row]

    def flow(self):
        return self.w.repo_dialogue.load(self.w.store.settings())

    def test_web_fetch_lists_real_branches_default_first_without_creating_monitor(self):
        client = create_app(watcher=self.w).test_client()
        headers = {'X-GitWatch':'1','Origin':'http://localhost'}
        response = client.post('/api/repos/branches',json={'url':'owner/project'},headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['branches'],['main','feature/sub','z-release'])
        self.assertEqual(response.json['default_branch'],'main')
        self.w.github.heads.assert_called_once_with({'full_name':'owner/project','mode':'all'})
        self.assertEqual(self.w.store.repos(),[])
        self.assertNotIn('secret',response.get_data(as_text=True))
        self.assertEqual(client.post('/api/repos/branches',json={'url':'owner/project'}).status_code,403)
        self.w.github.reset_mock()
        invalid = client.post('/api/repos/branches',json={'url':'https://evil.example/a/b'},headers=headers)
        self.assertEqual(invalid.status_code,400)
        self.w.github.metadata.assert_not_called()

    def test_bot_fetches_buttons_and_selected_branch_is_shared_with_site(self):
        self.send('/add owner/project')
        self.send('Выбрать ветку')
        self.assertEqual(self.buttons()[:3],['⑂ main','⑂ feature/sub','⑂ z-release'])
        self.assertIn('Основная: <code>main</code>',self.w._send.call_args.args[1])
        self.send('⑂ feature/sub')
        self.w.github.get.assert_called_with('/repos/owner/project/branches/feature%2Fsub')
        self.send('5 мин')
        self.assertEqual(self.w.snapshot()['repos'][0]['branch'],'feature/sub')

    def test_bot_paginates_cached_results_and_refreshes_changes(self):
        self.w.github.heads.return_value = {f'branch-{n:02d}':'a'*40 for n in range(BRANCH_PAGE_SIZE+3)}
        self.send('/add owner/project')
        self.send('Выбрать ветку')
        self.assertIn('Далее ›',self.buttons())
        self.assertNotIn('⑂ branch-10',self.buttons())
        self.send('Далее ›')
        self.assertIn('⑂ branch-10',self.buttons())
        self.assertIn('‹ Назад',self.buttons())
        self.assertNotIn('Далее ›',self.buttons())
        self.w.github.heads.assert_called_once()
        self.w.github.heads.return_value = {'new':'a'*40}
        self.send('↻ Обновить ветки')
        self.assertEqual(self.flow()['branch_page'],0)
        self.assertIn('⑂ new',self.buttons())
        self.assertNotIn('Далее ›',self.buttons())
        self.send('⑂ branch-10')
        self.assertEqual(self.flow()['stage'],'branch')
        self.assertIn('Выбери ветку из списка',self.w._send.call_args.args[1])

    def test_empty_or_unavailable_list_offers_retry_and_mode_navigation(self):
        self.w.github.heads.side_effect = RemoteError('GitHub unavailable')
        self.send('/add owner/project')
        self.send('Выбрать ветку')
        self.w.github.heads.assert_called_once()
        self.assertIn('↻ Обновить ветки',self.buttons())
        self.assertIn('GitHub unavailable',self.w._send.call_args.args[1])
        self.w.github.heads.side_effect = None
        self.w.github.heads.return_value = {}
        self.send('↻ Обновить ветки')
        self.assertIn('пока нет веток',self.w._send.call_args.args[1])
        self.send('← К выбору режима')
        self.send('Все ветки')
        self.send('5')
        self.assertEqual(self.w.store.repos()[0]['mode'],'all')

    def test_old_dialogue_resumes_with_loaded_buttons_and_reserved_branch_is_selectable(self):
        self.w.github.heads.return_value = {'Отмена':'a'*40}
        settings = self.w.store.settings()
        self.w.store.put_meta(FLOW_KEY,{'stage':'branch','mode':'branch','generation':settings['generation'],
            'chat_id':123,'updated_at':time.time(),'url':'https://github.com/owner/project','full_name':'owner/project'})
        self.send('/add')
        self.assertIn(BRANCH_PREFIX+'Отмена',self.buttons())
        self.send(BRANCH_PREFIX+'Отмена')
        self.assertEqual(self.flow()['stage'],'interval')
        self.assertEqual(self.flow()['branch'],'Отмена')


if __name__ == '__main__':
    unittest.main()
