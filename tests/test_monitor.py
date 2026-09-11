import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from gitwatch.clients import GitHub, InputError, RemoteError, Telegram, event_text, parse_repo
from gitwatch.service import Watcher
from gitwatch.web import create_app

A, B, C = 'a'*40, 'b'*40, 'c'*40


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.w = Watcher(self.temp.name)
        self.w.github = Mock()
        self.w.github.metadata.return_value = {'full_name':'owner/project','description':'Example'}
        self.w.github.details.return_value = {'summary':'Fix <edge> & retry','author':'dev','commit_count':2,'kind':'push'}
        self.w.telegram = Mock(proxies={'https':'http://proxy.invalid:8080'})
        self.w.telegram.call.return_value = {}
        self.w._send = Mock()

    def tearDown(self):
        self.temp.cleanup()

    def configure(self, **values):
        with self.w.store.transaction() as db:
            s = self.w.store.settings(db)
            s.update(values)
            self.w.store.save_settings(s,db)
        return self.w.store.settings()

    def add(self, **values):
        return self.w.add_repo({'url':'https://github.com/owner/project','interval_minutes':5,**values})['id']

    def check(self, repo_id, heads):
        self.w.github.heads.return_value = heads
        self.w.check_repo(repo_id)

    def message(self, username='owner', user_id=123, chat_id=123, chat_type='private', text='/start', date=None):
        return {'update_id':2,'message':{'date':date or int(time.time()),'from':{'id':user_id,'username':username},'chat':{'id':chat_id,'type':chat_type},'text':text}}

    def test_baseline_push_dedupe_and_restart(self):
        self.configure(telegram_token='secret',username='owner',chat_id=123)
        repo_id = self.add()
        self.check(repo_id,{'main':A})
        self.assertEqual(self.w.store.events(),[])
        self.check(repo_id,{'main':B})
        event = self.w.store.events()[0]
        self.assertEqual((event['old_sha'],event['sha'],event['delivery']),(A,B,'pending'))
        self.check(repo_id,{'main':B})
        restarted = Watcher(self.temp.name)
        restarted.github = self.w.github
        restarted.check_repo(repo_id)
        self.assertEqual(len(restarted.store.events()),1)
        self.w.deliver_once()
        self.assertEqual(self.w.store.events()[0]['delivery'],'sent')
        self.w.deliver_once()
        self.w._send.assert_called_once()

    def test_empty_repository_then_first_push(self):
        repo_id=self.add()
        self.check(repo_id,{})
        self.check(repo_id,{'main':A})
        self.assertEqual(self.w.store.events()[0]['kind'],'branch_created')

    def test_branch_create_delete_and_rewrite(self):
        repo_id=self.add()
        self.check(repo_id,{'main':A,'old':C})
        self.w.github.details.return_value['kind']='rewrite'
        self.check(repo_id,{'main':B,'new':C})
        self.assertEqual({e['kind'] for e in self.w.store.events()},{'rewrite','branch_created','branch_deleted'})

    def test_failed_read_does_not_advance_baseline(self):
        repo_id=self.add()
        self.check(repo_id,{'main':A})
        self.w.github.heads.side_effect=RemoteError('Limit',time.time()+5000,429)
        self.w.check_repo(repo_id)
        repo=self.w.store.repo(repo_id)
        self.assertEqual(json.loads(repo['heads']),{'main':A})
        self.assertGreater(repo['next_check'],time.time()+4900)
        self.assertEqual(self.w.store.events(),[])

    def test_invalid_response_never_deletes_existing_heads(self):
        repo_id=self.add()
        self.check(repo_id,{'main':A})
        self.check(repo_id,{'main':'not-a-sha'})
        self.assertEqual(json.loads(self.w.store.repo(repo_id)['heads']),{'main':A})

    def test_pause_resume_and_scope_change(self):
        repo_id=self.add()
        self.check(repo_id,{'main':A})
        self.w.update_repo(repo_id,{'revision':0,'enabled':False})
        self.check(repo_id,{'main':B})
        self.assertEqual(self.w.store.events(),[])
        self.w.update_repo(repo_id,{'revision':1,'enabled':True})
        self.check(repo_id,{'main':B})
        self.assertEqual(len(self.w.store.events()),1)
        self.w.update_repo(repo_id,{'revision':2,'mode':'branch','branch':'new'})
        self.check(repo_id,{'new':C})
        self.assertEqual(len(self.w.store.events()),1)

    def test_config_changed_during_poll_discards_stale_result(self):
        repo_id=self.add()
        self.check(repo_id,{'main':A})
        def heads(repo):
            self.w.update_repo(repo_id,{'revision':0,'mode':'branch','branch':'new'})
            return {'main':B}
        self.w.github.heads.side_effect=heads
        self.w.check_repo(repo_id)
        self.assertEqual(self.w.store.events(),[])
        self.assertFalse(self.w.store.repo(repo_id)['initialized'])

    def test_delivery_failure_is_durable_and_retryable(self):
        self.configure(telegram_token='secret',username='owner',chat_id=123)
        repo_id=self.add()
        self.check(repo_id,{'main':A})
        self.check(repo_id,{'main':B})
        self.w._send.side_effect=RemoteError('Offline')
        self.w.deliver_once()
        event=self.w.store.events()[0]
        self.assertEqual((event['delivery'],event['attempts']),('pending',1))
        with self.w.store.transaction() as db: db.execute('UPDATE events SET next_attempt=0')
        restarted=Watcher(self.temp.name)
        restarted._send=Mock()
        restarted.deliver_once()
        self.assertEqual(restarted.store.events()[0]['delivery'],'sent')

    def test_recipient_change_does_not_leak_pending_events(self):
        self.configure(telegram_token='secret',username='owner',chat_id=123)
        repo_id=self.add()
        self.check(repo_id,{'main':A})
        self.check(repo_id,{'main':B})
        self.configure(generation=1,username='other',chat_id=456)
        self.w.deliver_once()
        self.w._send.assert_not_called()
        self.assertEqual(self.w.store.events()[0]['delivery'],'skipped')

    def test_deletion_preserves_history_and_cancels_delivery(self):
        self.configure(telegram_token='secret',username='owner',chat_id=123)
        repo_id=self.add()
        self.check(repo_id,{'main':A})
        self.check(repo_id,{'main':B})
        self.w.remove_repo(repo_id)
        self.assertIsNone(self.w.store.events()[0]['repo_id'])
        self.assertEqual(self.w.store.events()[0]['delivery'],'skipped')

    def test_only_matching_personal_start_binds(self):
        settings=self.configure(telegram_token='secret',username='owner',binding_after=int(time.time()))
        for update in [self.message('outsider'),self.message(chat_type='group'),self.message(chat_id=-123),self.message(text='/status'),self.message(date=int(time.time())-100)]:
            self.assertFalse(self.w.process_update(update,settings))
        self.assertEqual(self.w.store.settings()['chat_id'],0)
        self.assertTrue(self.w.process_update(self.message('OwNeR'),settings))
        self.assertEqual(self.w.store.settings()['chat_id'],123)
        settings=self.w.store.settings()
        self.assertFalse(self.w.process_update(self.message(user_id=456,chat_id=456),settings))
        self.assertFalse(self.w.process_update(self.message(username='outsider'),settings))
        self.assertEqual(self.w._send.call_count,1)

    def test_telegram_proxy_applies_to_every_request_and_errors_hide_secrets(self):
        telegram=Telegram({'https':'http://user:secret@proxy.invalid:80'})
        with patch('gitwatch.clients.requests.post') as post:
            post.return_value.json.return_value={'ok':True,'result':{}}
            for method in ('getMe','getWebhookInfo','getUpdates','sendMessage'):
                telegram.call('private-token',method,{})
                self.assertEqual(post.call_args.kwargs['proxies'],telegram.proxies)
            import requests
            post.side_effect=requests.ProxyError if hasattr(requests,'ProxyError') else requests.exceptions.ProxyError('user:secret')
            with self.assertRaises(RemoteError) as raised: telegram.call('private-token','getMe',{})
            self.assertNotIn('secret',str(raised.exception))
            self.assertNotIn('private-token',str(raised.exception))

    def test_telegram_config_rejects_webhook_and_resets_binding(self):
        self.configure(telegram_token='1:'+'a'*30,username='owner',chat_id=123)
        def call(token,method,body):
            return {'is_bot':True,'username':'WatchBot'} if method=='getMe' else {'url':'https://example.com/webhook'}
        self.w.telegram.call.side_effect=call
        with self.assertRaises(InputError):self.w.configure_telegram({'token':'2:'+'b'*30,'username':'owner','revision':0})
        self.assertEqual(self.w.store.settings()['chat_id'],123)
        self.w.telegram.call.side_effect=lambda token,method,body: {'is_bot':True,'username':'WatchBot'} if method=='getMe' else {}
        self.w.configure_telegram({'token':'2:'+'b'*30,'username':'owner','revision':0})
        self.assertEqual(self.w.store.settings()['chat_id'],0)
        self.assertEqual(self.w.store.settings()['generation'],1)

    def test_poll_offsets_ignore_foreign_users(self):
        self.configure(telegram_token='secret',username='owner')
        self.w.telegram.call.return_value=[self.message('outsider')]
        self.w.telegram_once()
        self.assertEqual(self.w.store.settings()['offset'],3)
        self.assertEqual(self.w.store.settings()['chat_id'],0)

    def test_github_pagination_and_deleted_branch_access(self):
        gh=GitHub(self.w.store)
        gh.get=Mock(side_effect=[[{'name':f'b{i}','commit':{'sha':A}} for i in range(100)], [{'name':'last','commit':{'sha':B}}]])
        self.assertEqual(len(gh.heads({'full_name':'owner/project','mode':'all'})),101)
        self.assertIn('page=2',gh.get.call_args.args[0])
        gh.get=Mock(side_effect=[RemoteError('Not found',status=404),RemoteError('No access',status=404)])
        with self.assertRaises(RemoteError):gh.heads({'full_name':'owner/project','mode':'branch','branch':'main'})
        gh.get=Mock(side_effect=[RemoteError('Not found',status=404),{'full_name':'owner/project'}])
        self.assertEqual(gh.heads({'full_name':'owner/project','mode':'branch','branch':'main'}),{})

    def test_rate_limit_prevents_network_calls(self):
        gh=GitHub(self.w.store)
        self.w.store.put_meta('github',{'retry_at':time.time()+100})
        with patch('gitwatch.clients.requests.get') as get:
            with self.assertRaises(RemoteError):gh.get('/user')
            get.assert_not_called()

    def test_api_secret_redaction_csrf_and_crud(self):
        self.configure(github_token='GITHUB_SECRET',telegram_token='TELEGRAM_SECRET')
        client=create_app(watcher=self.w).test_client()
        output=client.get('/api/state').get_data(as_text=True)
        for secret in ('GITHUB_SECRET','TELEGRAM_SECRET','proxy.invalid'):
            self.assertNotIn(secret,output)
        self.assertEqual(client.post('/api/check',json={}).status_code,403)
        self.assertEqual(client.post('/api/check',json={},headers={'X-GitWatch':'1','Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(client.get('/api/state',headers={'Host':'evil.example'}).status_code,400)
        self.assertEqual(client.get('/data/gitwatch.sqlite3').status_code,404)
        h={'X-GitWatch':'1','Origin':'http://localhost'}
        response=client.post('/api/repos',json={'url':'owner/project'},headers=h)
        self.assertEqual(response.status_code,201)
        repo_id=response.json['id']
        self.assertEqual(client.patch(f'/api/repos/{repo_id}',json={'enabled':False,'revision':0},headers=h).status_code,200)
        self.assertEqual(client.patch(f'/api/repos/{repo_id}',json={'enabled':True,'revision':0},headers=h).status_code,400)
        self.assertEqual(client.delete(f'/api/repos/{repo_id}',json={},headers=h).status_code,200)
        self.assertEqual(client.get('/api/state').json['repos'],[])

    def test_invalid_input_and_safe_notification_html(self):
        for value in ('https://evil.example/x/y','https://github.com@evil.example/x/y','https://github.com/a/b/tree/main','../etc/passwd','a/..','https://github.com/a/b?token=secret'):
            with self.assertRaises(InputError):parse_repo(value)
        self.assertEqual(parse_repo('https://github.com/a/b.git/'),'a/b')
        for interval in (0,1441,True,1.5):
            with self.assertRaises(InputError):self.add(interval_minutes=interval)
        text=event_text({'kind':'push','full_name':'a/b','branch':'<script>','url':'https://github.com/a/b','summary':'<b>injection</b> & text','sha':A})
        self.assertIn('&lt;script&gt;',text)
        self.assertNotIn('<b>injection</b>',text)

    def test_backup_contains_pending_events_and_settings(self):
        self.configure(telegram_token='secret',username='owner')
        repo_id=self.add()
        self.check(repo_id,{'main':A})
        self.check(repo_id,{'main':B})
        destination=Path(self.temp.name)/'backup.sqlite3'
        self.w.store.backup(destination)
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(destination)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],1)


if __name__=='__main__':
    unittest.main()
