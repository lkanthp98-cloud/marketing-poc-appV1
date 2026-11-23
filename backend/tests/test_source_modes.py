"""Exercise Gold connections and migration of legacy source preferences using an isolated simulated live warehouse."""
import re
import sqlite3
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app,store,ConnectionSettings
from backend.store import ACTIVE_CONNECTION,DataError,WORKSPACE_CONTRACT,Store,identifier,preview_database


class SourceModeTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app,base_url='https://testserver')
        self.headers={'x-forwarded-access-token':'source-mode-user'}
        self.queries=[]
        self.partial=False

    def warehouse(self,sql,params,user):
        self.queries.append(sql)
        if '.information_schema.columns ' in sql:
            if 'column_name AS name' in sql:
                location=('source-data.usecases.' if '`source-data`' in sql else 'media-poc.gold.')+params['name']
                declared=WORKSPACE_CONTRACT['tables'][location]['columns']
                conn=sqlite3.connect(preview_database())
                try:present={row[1] for row in conn.execute('PRAGMA table_info('+identifier(params['name'])+')')}
                finally:conn.close()
                return [c for c in declared if c['name'] in present]
            return [{'table_catalog':t['catalog'],'table_schema':t['schema'],'table_name':t['name'],
                'column_name':c['name'],'full_data_type':c['type']} for t in WORKSPACE_CONTRACT['tables'].values()
                if t['schema'] in params.values() and ('`'+t['catalog']+'`') in sql for c in t['columns']]
        translated=re.sub(r'`(?:media-poc|source-data)`\.`(?:gold|usecases)`\.','',sql).replace(' AS STRING)',' AS TEXT)')
        conn=sqlite3.connect(preview_database());conn.row_factory=sqlite3.Row
        try:rows=[dict(row) for row in conn.execute(translated,params).fetchall()]
        except sqlite3.Error as error:raise DataError('Simulated warehouse: '+str(error)) from error
        finally:conn.close()
        if self.partial and 'FROM `media-poc`.`gold`.`gold_mart_catalog`' in sql:
            rows=[r for r in rows if r['mart_table']!='mart_demo_campaign_economics']
        return rows

    def select(self,mode):
        body={'source_mode':mode}
        if mode in {'gold','both'}:body.update(gold_catalog='media-poc',gold_schema='gold')
        if mode in {'use_cases','both'}:body.update(use_cases_catalog='source-data',use_cases_schema='usecases')
        response=self.client.post('/api/connection',json=body,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def run_mode(self,mode):
        with patch.object(store,'mode','live'),patch.object(store,'query',side_effect=self.warehouse):
            result=self.select(mode)
            self.assertEqual(set(result['verified_source_objects']),{'gold'})
            response=self.client.get('/api/bootstrap',headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            bootstrap=response.json()
            layer='gold'
            self.assertEqual(bootstrap['analytics_layer'],layer)
            self.assertEqual(bootstrap['sources'],91)
            for page in ['overview','campaigns','acquisition','digital','finance','experiments']:
                response=self.client.get('/api/dashboard/'+page,headers=self.headers)
                self.assertEqual(response.status_code,200,response.text)
                self.assertTrue(all(m['source'].startswith('media-poc.gold.' if layer=='gold' else 'source-data.usecases.') for m in response.json()['metrics']))
            name='mart_vendor_media_daily' if layer=='gold' else 'uc02_vendor_media_daily'
            for endpoint in ['schema','table','export']:
                response=self.client.get(f'/api/{endpoint}/{name}?layer={layer}',headers=self.headers)
                self.assertEqual(response.status_code,200,response.text)
            for kind in ['readiness','metrics','lineage']:
                response=self.client.get('/api/metadata/'+kind,headers=self.headers)
                self.assertEqual(response.status_code,200,response.text)
            response=self.client.get('/api/workspace-schema',headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
        if mode=='gold':self.assertFalse(any('`source-data`.`usecases`' in q or '`source-data`.information_schema' in q for q in self.queries))
        self.assertFalse(any('`source-data`' in q or '.`usecases`.' in q for q in self.queries))
        self.assertEqual(ACTIVE_CONNECTION.get(),{})

    def test_gold_only_has_no_use_cases_dependency(self):self.run_mode('gold')
    def test_legacy_use_cases_cookie_migrates_to_configured_gold(self):self.run_mode('use_cases')
    def test_legacy_both_cookie_uses_gold_only(self):self.run_mode('both')

    def test_deployment_default_source_mode_requires_no_browser_cookie(self):
        for mode in ['gold','use_cases','both']:
            with patch.dict(os.environ,{'DATA_SOURCE_MODE':mode}):
                instance=Store()
                self.assertEqual(instance.connection()['source_mode'],'gold')
                self.assertEqual(instance.analytics_layer,'gold')

    def test_disabled_source_fields_are_optional_and_ignored(self):
        self.assertEqual(ConnectionSettings(source_mode='gold',gold_catalog='media-poc',gold_schema='gold').profile()['use_cases_catalog'],'')
        self.assertEqual(ConnectionSettings(source_mode='use_cases',use_cases_catalog='source-data',use_cases_schema='usecases').profile()['gold_catalog'],'media-poc')
        with self.assertRaises(DataError):ConnectionSettings(source_mode='gold').profile()

    def test_warehouse_failure_is_reported_before_either_source_is_read(self):
        captured=[]
        def denied(sql,*args):
            captured.append(sql);raise DataError('SQL API rejected this request. Enable sql scope and warehouse CAN USE.',403)
        with patch.object(store,'mode','live'),patch.object(store,'query',side_effect=denied):
            response=self.client.post('/api/connection',json={'source_mode':'use_cases','use_cases_catalog':'source-data','use_cases_schema':'usecases'},headers=self.headers)
        self.assertEqual(response.status_code,403)
        self.assertIn('before any source was read',response.text)
        self.assertEqual(captured,['SELECT 1 AS connection_ok'])

    def test_partial_publication_keeps_working_metrics_and_does_not_read_stale_tables(self):
        self.partial=True
        with patch.object(store,'mode','live'),patch.object(store,'query',side_effect=self.warehouse):
            self.select('gold');self.queries.clear()
            response=self.client.get('/api/dashboard/overview',headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        metrics=response.json()['metrics']
        self.assertIsNotNone(metrics[0]['value'])
        self.assertIsNone(metrics[1]['value'])
        self.assertIn('not registered',metrics[1]['unavailable_reason'])
        self.assertFalse(any('FROM `media-poc`.`gold`.`mart_demo_campaign_economics`' in q for q in self.queries))

    def test_denied_source_names_the_selected_layer(self):
        def denied(sql,*args):
            if sql.startswith('SELECT 1'):return [{'connection_ok':1}]
            raise DataError('PERMISSION_DENIED on selected metadata',403)
        with patch.object(store,'mode','live'),patch.object(store,'query',side_effect=denied):
            response=self.client.post('/api/connection',json={'source_mode':'use_cases','use_cases_catalog':'source-data','use_cases_schema':'usecases'},headers=self.headers)
        self.assertEqual(response.status_code,403)
        self.assertIn('gold source metadata access failed',response.text)
        self.assertNotIn('Gold table access',response.text)


if __name__=='__main__':unittest.main()
