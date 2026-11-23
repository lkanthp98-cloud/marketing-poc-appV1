"""Exercise explicit M2M vs viewer auth, bounded shared access, and owner-only setup."""
import importlib.util
import io
import json
import os
import unittest
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock,patch

from backend.main import store
from backend.store import APP_ROOT,APP_TABLES,ACTIVE_CONNECTION,DataError,Store
from backend.tests import test_app_subset as subset_tests

helper_spec=importlib.util.spec_from_file_location('configure_app_read_access',APP_ROOT/'scripts/configure_app_read_access.py')
helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)


class AppOAuthTests(unittest.TestCase):
    def runtime(self,mode):
        with patch.dict(os.environ,{'DATA_MODE':'live','SQL_AUTH_MODE':mode,'DATABRICKS_HOST':'workspace.example',
            'DATABRICKS_WAREHOUSE_ID':'wh-123','GOLD_CATALOG':'source-data','GOLD_SCHEMA':'app_gold'}):return Store()

    def response(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"ok":true}'
        return response

    def test_app_mode_uses_only_managed_m2m_credentials_and_reuses_sdk_refresh_provider(self):
        runtime=self.runtime('app')
        with patch.dict(os.environ,{'DATABRICKS_CLIENT_ID':'app-client','DATABRICKS_CLIENT_SECRET':'managed-secret',
             'DATABRICKS_TOKEN':'ignored-personal-token'}),patch('databricks.sdk.core.Config') as config,\
             patch('urllib.request.urlopen',return_value=self.response()) as request:
            config.return_value.authenticate.side_effect=[{'Authorization':'Bearer app-one'},{'Authorization':'Bearer app-two'}]
            runtime._request('/api/2.0/sql/statements','forbidden-user-token',{})
            runtime._request('/api/2.0/sql/statements/statement-1','forbidden-user-token')
            config.assert_called_once_with(host='https://workspace.example',client_id='app-client',
                client_secret='managed-secret',auth_type='oauth-m2m')
            self.assertEqual([c.args[0].get_header('Authorization') for c in request.call_args_list],
                ['Bearer app-one','Bearer app-two'])

    def test_missing_app_credentials_never_uses_a_viewer_token(self):
        runtime=self.runtime('app')
        with patch.dict(os.environ,{'DATABRICKS_CLIENT_ID':'','DATABRICKS_CLIENT_SECRET':''}),\
             patch('urllib.request.urlopen') as request:
            with self.assertRaisesRegex(DataError,'credentials were not injected'):
                runtime._request('/api/2.0/sql/statements','otherwise-valid-user-token',{})
            request.assert_not_called()

    def test_user_403_is_not_retried_as_app_identity_and_includes_platform_error(self):
        runtime=self.runtime('user')
        error=urllib.error.HTTPError('https://workspace.example',403,'Forbidden',{},
            io.BytesIO(b'{"error_code":"MISSING_SCOPE","message":"SQL permission is missing"}'))
        with patch.object(runtime,'_app_headers') as app_headers,patch('urllib.request.urlopen',side_effect=error) as request:
            with self.assertRaises(DataError) as caught:runtime._request('/api/2.0/sql/statements','viewer-token',{})
        self.assertEqual(caught.exception.status,403)
        self.assertIn('User SQL mode',str(caught.exception));self.assertIn('MISSING_SCOPE',str(caught.exception))
        app_headers.assert_not_called();self.assertEqual(request.call_count,1)

    def test_app_403_has_app_grant_guidance_without_leaking_any_credentials(self):
        runtime=self.runtime('app')
        app_token='app-oauth-token-'+('X'*1200)
        viewer_token='viewer-token-'+('Y'*900)
        client_secret='managed-secret-'+('Z'*900)
        message=app_token+' '+viewer_token+' '+client_secret
        error=urllib.error.HTTPError('https://workspace.example',403,'Forbidden',{},
            io.BytesIO(json.dumps({'error_code':'PERMISSION_DENIED','message':message}).encode()))
        with patch.dict(os.environ,{'DATABRICKS_CLIENT_SECRET':client_secret}),\
             patch.object(runtime,'_app_headers',return_value={'Authorization':'Bearer '+app_token}),\
             patch('urllib.request.urlopen',side_effect=error) as request:
            with self.assertRaises(DataError) as caught:runtime._request('/api/2.0/sql/statements',viewer_token,{})
        text=str(caught.exception)
        self.assertIn('App SQL mode',text);self.assertIn('PERMISSION_DENIED',text)
        for secret in [app_token,viewer_token,client_secret]:self.assertNotIn(secret[:40],text)
        self.assertEqual(request.call_count,1)

    def test_sdk_failure_is_sanitized_and_never_falls_back(self):
        runtime=self.runtime('app')
        with patch.dict(os.environ,{'DATABRICKS_CLIENT_ID':'client','DATABRICKS_CLIENT_SECRET':'secret'}),\
             patch('databricks.sdk.core.Config',side_effect=ValueError('secret credential detail')),\
             patch('urllib.request.urlopen') as request:
            with self.assertRaises(DataError) as caught:runtime._request('/api/2.0/sql/statements','viewer',{})
        self.assertNotIn('secret credential detail',str(caught.exception));request.assert_not_called()

    def test_app_mode_ignores_other_namespace_preferences_and_blocks_non_subset_tables(self):
        runtime=self.runtime('app');token=ACTIVE_CONNECTION.set({'gold_catalog':'another','gold_schema':'private'})
        try:
            self.assertEqual(runtime.table('dim_campaign'),'`source-data`.`app_gold`.`dim_campaign`')
            with self.assertRaisesRegex(DataError,'outside the configured'):runtime.table('dim_customer')
            with self.assertRaisesRegex(DataError,'bound to the configured'):
                runtime.validate_connection({'gold_catalog':'another','gold_schema':'private'})
        finally:ACTIVE_CONNECTION.reset(token)

    def test_unknown_mode_is_rejected_and_safe_diagnostics_expose_no_secrets(self):
        with patch.dict(os.environ,{'SQL_AUTH_MODE':'automatic'}),self.assertRaises(RuntimeError):Store()
        runtime=self.runtime('app')
        with patch.dict(os.environ,{'DATABRICKS_CLIENT_ID':'private-client','DATABRICKS_CLIENT_SECRET':'private-secret'}):
            result=runtime.runtime_status()
        self.assertTrue(result['app_client_id_present']);self.assertTrue(result['app_client_secret_present'])
        self.assertTrue(result['shared_app_dataset']);self.assertNotIn('private-',json.dumps(result))


class SharedAppRouteTests(unittest.TestCase):
    setUp=subset_tests.SubsetAppTests.setUp
    tearDown=subset_tests.SubsetAppTests.tearDown
    warehouse=subset_tests.SubsetAppTests.warehouse
    _warehouse_read=subset_tests.SubsetAppTests._warehouse_read
    def test_shared_dataset_opens_without_forwarded_user_sql_token_and_cannot_be_redirected(self):
        self.client.cookies.set('marketing_connection','invalid-old-cookie')
        defaults={**store._defaults,'gold_catalog':'source-data','gold_schema':'app_gold'}
        with patch.object(store,'mode','live'),patch.object(store,'sql_auth_mode','app'),\
             patch.object(store,'_defaults',defaults),patch.object(store,'query',side_effect=self.warehouse):
            bootstrap=self.client.get('/api/bootstrap')
            self.assertEqual(bootstrap.status_code,200,bootstrap.text)
            self.assertTrue(bootstrap.json()['shared_data'])
            self.assertEqual(len(bootstrap.json()['tables']),30)
            for page in ['overview','campaigns','acquisition','digital','finance','experiments']:
                result=self.client.get('/api/dashboard/'+page)
                self.assertEqual(result.status_code,200,result.text)
                self.assertTrue(all(m['value'] is not None for m in result.json()['metrics']))
            result=self.client.post('/api/connection',json={'gold_catalog':'source-data','gold_schema':'app_gold'})
            self.assertEqual(result.status_code,200,result.text)
            count=len(self.queries)
            denied=self.client.post('/api/connection',json={'gold_catalog':'media-poc','gold_schema':'gold'})
            self.assertEqual(denied.status_code,400,denied.text);self.assertEqual(len(self.queries),count)
            schema=self.client.get('/api/workspace-schema')
            self.assertEqual(schema.status_code,200,schema.text);self.assertEqual(len(schema.json()['tables']),30)
            genie=self.client.post('/api/genie/messages',json={'question':'Spend?'})
            self.assertEqual(genie.status_code,401,genie.text)
            self.assertIn('independently',genie.text)


class SetupGrantTests(unittest.TestCase):
    def client(self):
        client=MagicMock();client.apps.get.return_value=SimpleNamespace(service_principal_client_id='12345678-1234-1234-1234-123456789012')
        return client

    def test_setup_resolves_existing_app_and_grants_only_subset_read_access(self):
        client=self.client()
        inventory={'status':{'state':'SUCCEEDED'},'result':{'data_array':[[n] for n in sorted(APP_TABLES)]}}
        with patch.object(helper,'execute',side_effect=[inventory]+[{'status':{'state':'SUCCEEDED'}}]*3) as execute:
            result=helper.configure(client,'marketing-intelligence','warehouse-1')
        client.apps.get.assert_called_once_with(name='marketing-intelligence')
        grants=[c.args[2] for c in execute.call_args_list[1:]]
        self.assertTrue(grants[0].startswith('GRANT USE CATALOG ON CATALOG `source-data`'))
        self.assertTrue(grants[1].startswith('GRANT USE SCHEMA ON SCHEMA `source-data`.`app_gold`'))
        self.assertTrue(grants[2].startswith('GRANT SELECT ON SCHEMA `source-data`.`app_gold`'))
        self.assertEqual(result['grants'],3)
        self.assertFalse(any('MODIFY' in s or 'CREATE' in s or 'DROP' in s for s in grants))

    def test_setup_refuses_an_unexpected_schema_without_granting_anything(self):
        with patch.object(helper,'execute',return_value={'result':{'data_array':[['another_table']]}}) as execute:
            with self.assertRaisesRegex(ValueError,'exactly the 30 app tables'):
                helper.configure(self.client(),'marketing-intelligence','warehouse-1')
        self.assertEqual(execute.call_count,1)


if __name__=='__main__':unittest.main()
