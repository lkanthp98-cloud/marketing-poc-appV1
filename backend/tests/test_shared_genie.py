"""Share-link access: app OAuth for Genie, private sessions, and no viewer data grants."""
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch,MagicMock
from fastapi.testclient import TestClient

from backend import genie,session
from backend.main import app,store
from backend.store import Store,Viewer,DataError


class BrowserSessionTests(unittest.TestCase):
    def test_signed_session_is_stable_and_tampering_or_malformed_input_rotates_it(self):
        token,cookie,new=session.resolve('')
        self.assertTrue(new)
        self.assertEqual(session.resolve(cookie),(token,cookie,False))
        for bad in [cookie[:-1]+('0' if cookie[-1]!='0' else '1'),'abc','x.'+'\u2603'*64]:
            next_token,next_cookie,changed=session.resolve(bad)
            self.assertTrue(changed);self.assertNotEqual(token,next_token)

    def test_app_proof_binds_browser_account_space_and_mode_not_rotating_user_tokens(self):
        with patch.dict(os.environ,{'GENIE_SPACE_ID':'space-123'}):
            alice=Viewer('old-user-token',session_key='browser-a',actor='alice')
            key=genie.proof(alice,'conversation-1','app')
            genie.authorize(Viewer('new-user-token',session_key='browser-a',actor='alice'),'conversation-1',key,'app')
            for other in [Viewer(session_key='browser-b',actor='alice'),Viewer(session_key='browser-a',actor='bob')]:
                with self.assertRaises(DataError):genie.authorize(other,'conversation-1',key,'app')
            with self.assertRaises(DataError):genie.authorize(alice,'conversation-1',key,'user')
            with patch.dict(os.environ,{'GENIE_SPACE_ID':'other-space'}),self.assertRaises(DataError):
                genie.authorize(alice,'conversation-1',key,'app')


class GenieAppOAuthTests(unittest.TestCase):
    def runtime(self,mode):
        with patch.dict(os.environ,{'DATA_MODE':'live','SQL_AUTH_MODE':'app','GENIE_AUTH_MODE':mode,
            'DATABRICKS_HOST':'workspace.example'}):return Store()

    def test_app_genie_uses_managed_app_headers_without_forwarded_user_token(self):
        runtime=self.runtime('app')
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"status":"SUBMITTED"}'
        with patch.dict(os.environ,{'GENIE_SPACE_ID':'space-123'}),\
             patch.object(runtime,'_app_headers',return_value={'Authorization':'Bearer app-token'}) as auth,\
             patch('urllib.request.urlopen',return_value=response) as request:
            genie.request(runtime,Viewer(session_key='private-session'),'/start-conversation',{'content':'Spend?'})
        auth.assert_called_once()
        sent=request.call_args.args[0]
        self.assertEqual(sent.get_header('Authorization'),'Bearer app-token')
        self.assertIsNone(sent.get_header('Cookie'))

    def test_user_genie_still_rejects_missing_user_token_without_app_fallback(self):
        runtime=self.runtime('user')
        with patch.object(runtime,'_app_headers') as auth,self.assertRaisesRegex(DataError,'Genie user mode'):
            genie.request(runtime,Viewer(),'/start-conversation')
        auth.assert_not_called()

    def test_app_genie_403_preserves_platform_detail_and_has_app_grant_guidance(self):
        runtime=self.runtime('app')
        error=urllib.error.HTTPError('https://workspace.example',403,'Forbidden',{},
            io.BytesIO(b'{"error_code":"PERMISSION_DENIED","message":"Bearer app-token is not allowed"}'))
        with patch.dict(os.environ,{'GENIE_SPACE_ID':'space-123'}),\
             patch.object(runtime,'_app_headers',return_value={'Authorization':'Bearer app-token'}),\
             patch('urllib.request.urlopen',side_effect=error) as request:
            with self.assertRaises(DataError) as caught:genie.request(runtime,Viewer(),'/start-conversation')
        self.assertIn('Genie app mode',str(caught.exception))
        self.assertIn('PERMISSION_DENIED',str(caught.exception));self.assertNotIn('app-token',str(caught.exception))
        self.assertEqual(request.call_count,1)


class GenieSharedRouteTests(unittest.TestCase):
    def test_no_viewer_scopes_required_and_stolen_conversation_key_cannot_cross_sessions(self):
        alice=TestClient(app,base_url='https://testserver');bob=TestClient(app,base_url='https://testserver')
        response={'conversation_id':'conv-1','message_id':'msg-1','status':'SUBMITTED'}
        alice_headers={'x-forwarded-user':'proxy-subject','x-forwarded-email':'alice'}
        bob_headers={'x-forwarded-user':'proxy-subject','x-forwarded-email':'bob'}
        with patch.object(store,'mode','live'),patch.object(store,'sql_auth_mode','app'),\
             patch.object(store,'genie_auth_mode','app'),patch.dict(os.environ,{'GENIE_SPACE_ID':'space-123'}),\
             patch.object(genie,'request',return_value=response) as request:
            config=alice.get('/api/genie/config',headers=alice_headers)
            self.assertEqual(config.status_code,200,config.text)
            self.assertEqual(config.json()['auth_mode'],'app')
            self.assertIn('HttpOnly',config.headers['set-cookie']);self.assertIn('Secure',config.headers['set-cookie'])
            self.assertIn('SameSite=lax',config.headers['set-cookie'])
            first=alice.post('/api/genie/messages',json={'question':'Spend?'},headers=alice_headers)
            self.assertEqual(first.status_code,200,first.text)
            key=first.json()['conversation_key']
            payload={'question':'Follow up','conversation_id':'conv-1','conversation_key':key}
            before=request.call_count
            stolen=bob.post('/api/genie/messages',json=payload,headers=bob_headers)
            self.assertEqual(stolen.status_code,403,stolen.text)
            self.assertEqual(request.call_count,before)
            switched=alice.post('/api/genie/messages',json=payload,headers=bob_headers)
            self.assertEqual(switched.status_code,403,switched.text)
            self.assertEqual(request.call_count,before)
            follow=alice.post('/api/genie/messages',json=payload,headers=alice_headers)
            self.assertEqual(follow.status_code,200,follow.text)
            with patch.object(genie,'request',return_value={'status':'COMPLETED','attachments':[]}):
                poll=alice.get('/api/genie/messages/conv-1/msg-1',params={'key':key},headers=alice_headers)
                self.assertEqual(poll.status_code,200,poll.text)
                stolen_poll=bob.get('/api/genie/messages/conv-1/msg-1',params={'key':key},headers=bob_headers)
                self.assertEqual(stolen_poll.status_code,403,stolen_poll.text)
            self.assertNotIn('session_key',first.json())


if __name__=='__main__':unittest.main()
