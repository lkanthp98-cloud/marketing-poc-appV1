import json
import os
import unittest
from unittest.mock import patch,MagicMock
from backend.store import Store,DataError,normalize_workspace_host
from backend import genie
from backend.store import Viewer


class RuntimeTests(unittest.TestCase):
    def runtime(self,**values):
        baseline={'DATABRICKS_HOST':'','DATABRICKS_WAREHOUSE_ID':'','DATABRICKS_SQL_WAREHOUSE_ID':'',
            'WAREHOUSE_ID':'','DATA_MODE':'live','GENIE_SPACE_ID':'space-123'}
        with patch.dict(os.environ,{**baseline,**values}):return Store()

    def test_documented_schemeless_and_https_hosts_have_same_origin(self):
        for value in ['adb-example.azuredatabricks.net','https://adb-example.azuredatabricks.net',
            '  adb-example.azuredatabricks.net/  ','HTTPS://adb-example.azuredatabricks.net/']:
            with self.subTest(value=value):self.assertEqual(normalize_workspace_host(value),'https://adb-example.azuredatabricks.net')
        for value in ['http://workspace.example','https://name:password@workspace.example','https://workspace.example/path',
            'https://workspace.example/?o=123','workspace example','https://workspace.example:wrong']:
            with self.subTest(value=value),self.assertRaises(ValueError):normalize_workspace_host(value)

    def test_attached_warehouse_is_not_rejected_due_to_host_scheme(self):
        runtime=self.runtime(DATABRICKS_HOST='workspace.example',DATABRICKS_WAREHOUSE_ID='warehouse-123')
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"status":"ok"}'
        with patch('urllib.request.urlopen',return_value=response) as open_url:
            self.assertEqual(runtime._request('/api/2.0/sql/statements','viewer-token',{}),{'status':'ok'})
        request=open_url.call_args.args[0]
        self.assertEqual(request.full_url,'https://workspace.example/api/2.0/sql/statements')
        self.assertEqual(request.get_header('Authorization'),'Bearer viewer-token')

    def test_warehouse_aliases_and_canonical_precedence(self):
        for name in ['DATABRICKS_WAREHOUSE_ID','DATABRICKS_SQL_WAREHOUSE_ID','WAREHOUSE_ID']:
            runtime=self.runtime(DATABRICKS_HOST='workspace.example',**{name:' wh-123 '})
            runtime.validate_runtime();self.assertEqual(runtime.warehouse,'wh-123')
            self.assertEqual(runtime.warehouse_env,name)
        runtime=self.runtime(DATABRICKS_HOST='workspace.example',DATABRICKS_WAREHOUSE_ID='canonical',WAREHOUSE_ID='other')
        self.assertEqual(runtime.warehouse,'canonical')

    def test_separate_host_and_resource_errors_before_network(self):
        for runtime,message in [
            (self.runtime(DATABRICKS_WAREHOUSE_ID='wh'),'DATABRICKS_HOST is missing'),
            (self.runtime(DATABRICKS_HOST='http://workspace.example',DATABRICKS_WAREHOUSE_ID='wh'),'DATABRICKS_HOST is invalid'),
            (self.runtime(DATABRICKS_HOST='workspace.example'),'warehouse ID was not injected')]:
            with patch('urllib.request.urlopen') as request:
                with self.assertRaisesRegex(DataError,message):runtime._request('/api/2.0/sql/statements','token')
                request.assert_not_called()

    def test_diagnostics_exclude_environment_values_and_credentials(self):
        runtime=self.runtime(DATABRICKS_HOST='private-workspace.example',DATABRICKS_WAREHOUSE_ID='private-warehouse')
        result=runtime.runtime_status();text=json.dumps(result)
        self.assertTrue(result['workspace_host_valid']);self.assertTrue(result['warehouse_id_present'])
        self.assertNotIn('private-workspace',text);self.assertNotIn('private-warehouse',text)
        self.assertNotIn('DATABRICKS_CLIENT_SECRET',text)

    def test_genie_uses_the_same_normalized_host(self):
        runtime=self.runtime(DATABRICKS_HOST='workspace.example')
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"conversation_id":"c"}'
        with patch.dict(os.environ,{'GENIE_SPACE_ID':'space-123'}),patch('urllib.request.urlopen',return_value=response) as open_url:
            genie.request(runtime,Viewer('viewer-token'),'/start-conversation',{'content':'spend?'})
        self.assertTrue(open_url.call_args.args[0].full_url.startswith('https://workspace.example/api/2.0/genie/'))


if __name__=='__main__':unittest.main()
