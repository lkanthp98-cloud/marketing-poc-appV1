"""Check the exact app subset, metadata integrity and all pages without source-Gold access."""
import copy
import importlib.util
import json
import re
import sqlite3
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.catalog import PAGES, DATE_FIELDS, META_TABLES
from backend.main import app, store
from backend.store import ANALYTICS_MAPPING, APP_ROOT, DataError, identifier, preview_database

spec=importlib.util.spec_from_file_location('app_subset_publisher',APP_ROOT/'notebooks/08_publish_app_gold_subset.py')
publisher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class SubsetContractTests(unittest.TestCase):
    def metadata(self):
        conn=sqlite3.connect(preview_database());conn.row_factory=sqlite3.Row
        try:
            records={n:[dict(r) for r in conn.execute('SELECT * FROM '+identifier(n))] for n in publisher.METADATA}
            counts={n:conn.execute('SELECT COUNT(*) FROM '+identifier(n)).fetchone()[0] for n in publisher.DATA_TABLES}
        finally:conn.close()
        return records,counts

    def test_exact_allowlist_covers_every_dashboard_record_and_startup_dependency(self):
        marts={m.table for p in PAGES.values() for m in p['metrics']}|{c.table for p in PAGES.values() for c in p['charts']}
        marts|={p['table'] for p in PAGES.values()}|(set(DATE_FIELDS)&set(ANALYTICS_MAPPING))
        marts.add('mart_demo_paid_media_daily')
        self.assertEqual(set(publisher.MARTS),marts)
        self.assertEqual(len(publisher.MARTS),23)
        self.assertEqual(set(publisher.METADATA),META_TABLES)
        self.assertEqual(len(set(publisher.TABLES)),30)

    def test_metadata_only_advertises_copied_tables_and_keeps_snapshot_counts(self):
        source,counts=self.metadata();original=copy.deepcopy(source)
        output=publisher.prepare_metadata(source,counts)
        self.assertEqual(source,original)
        self.assertEqual(len(output['gold_mart_catalog']),23)
        self.assertEqual(len(output['gold_entity_catalog']),1)
        for row in output['gold_mart_catalog']:self.assertEqual(row['row_count'],counts[row['mart_table']])
        self.assertTrue(output['gold_source_coverage'])
        for row in output['gold_source_coverage']:
            self.assertTrue(set(publisher.references(row['gold_tables']))<=set(publisher.DATA_TABLES))
        self.assertEqual({row['use_case'] for row in output['gold_use_case_readiness']},{'UC'+str(i).zfill(2) for i in range(1,11)})
        self.assertEqual(output['gold_kpi_dictionary'],source['gold_kpi_dictionary'])

    def test_lineage_rebases_retained_fact_dependencies_to_their_published_marts(self):
        source,counts=self.metadata()
        output=publisher.prepare_metadata(source,counts)
        vendor_sources={r['dq_table'] for r in source['gold_source_coverage'] if 'fact_vendor_delivery' in publisher.references(r['gold_tables'])}
        self.assertTrue(vendor_sources)
        for row in output['gold_source_coverage']:
            if row['dq_table'] in vendor_sources:
                self.assertIn('mart_vendor_media_daily',publisher.references(row['gold_tables']))
                self.assertNotIn('fact_vendor_delivery',publisher.references(row['gold_tables']))

    def test_array_metadata_works_with_native_spark_arrays_and_notes_excluded_marts(self):
        source,counts=self.metadata()
        for name,field in [('gold_source_coverage','gold_tables'),('gold_source_coverage','use_cases'),('gold_use_case_readiness','reporting_marts')]:
            for row in source[name]:row[field]=publisher.references(row[field])
        result=publisher.prepare_metadata(source,counts)
        self.assertTrue(all(isinstance(r['gold_tables'],list) for r in result['gold_source_coverage']))
        uc02=next(r for r in result['gold_use_case_readiness'] if r['use_case']=='UC02')
        self.assertNotIn('mart_demo_paid_reach_window',uc02['reporting_marts'])
        self.assertIn('mart_demo_paid_reach_window',uc02['remaining_requirements'])
        self.assertEqual(uc02['implementation_status'],'limited_app_subset')

    def test_capacity_includes_new_tables_and_known_additional_objects_and_reruns(self):
        self.assertEqual(publisher.capacity_plan(377,set())['projected_objects'],407)
        self.assertEqual(publisher.capacity_plan(407,set(publisher.TABLES))['new_tables'],0)
        with self.assertRaisesRegex(ValueError,'BEFORE writes'):publisher.capacity_plan(480,set(),500)
        with self.assertRaisesRegex(ValueError,'BEFORE writes'):publisher.capacity_plan(377,set(),450,50)
        with self.assertRaises(ValueError):publisher.capacity_plan(0,set(),501)

    def test_missing_or_duplicate_source_inventory_fails_before_publication(self):
        source,counts=self.metadata()
        source['gold_mart_catalog']=[r for r in source['gold_mart_catalog'] if r['mart_table']!='mart_vendor_media_daily']
        with self.assertRaisesRegex(ValueError,'Missing or duplicate'):publisher.prepare_metadata(source,counts)

    def test_unowned_targets_are_never_replaced(self):
        with self.assertRaisesRegex(ValueError,'not owned'):
            publisher.validate_target(True,{'format':'delta','properties':{}},'media-poc.gold.dim_campaign')
        publisher.validate_target(True,{'format':'delta','properties':{
            'marketing.app_subset.owner':publisher.OWNER,'marketing.app_subset.source':'media-poc.gold.dim_campaign'}},
            'media-poc.gold.dim_campaign')

    def test_copy_sql_has_only_target_mutation_and_snapshot_lineage(self):
        sql=publisher.create_sql('`source-data`.`app_gold`.`dim_campaign`',
            'SELECT * FROM `media-poc`.`gold`.`dim_campaign` VERSION AS OF 12',
            'media-poc.gold.dim_campaign',12,'test-run')
        self.assertTrue(sql.startswith('CREATE OR REPLACE TABLE `source-data`.`app_gold`.`dim_campaign`'))
        self.assertIn('VERSION AS OF 12',sql)
        self.assertIn("'marketing.app_subset.source_version'='12'",sql)
        for unsafe in ["a'b",'a`b','a\\b']:
            with self.assertRaises(ValueError):
                publisher.namespace(unsafe,'app_gold');publisher.literal(unsafe)


class SubsetAppTests(unittest.TestCase):
    def setUp(self):
        self.query_lock=threading.RLock()
        self.conn=sqlite3.connect(':memory:',check_same_thread=False);self.conn.row_factory=sqlite3.Row
        self.conn.execute('ATTACH DATABASE ? AS original',(str(preview_database()),))
        for name in publisher.DATA_TABLES:
            self.conn.execute('CREATE TABLE '+identifier(name)+' AS SELECT * FROM original.'+identifier(name))
        counts={n:self.conn.execute('SELECT COUNT(*) FROM '+identifier(n)).fetchone()[0] for n in publisher.DATA_TABLES}
        metadata={n:[dict(r) for r in self.conn.execute('SELECT * FROM original.'+identifier(n))] for n in publisher.METADATA}
        self.records=publisher.prepare_metadata(metadata,counts)
        for name in publisher.METADATA:
            self.conn.execute('CREATE TABLE '+identifier(name)+' AS SELECT * FROM original.'+identifier(name)+' WHERE 0')
            fields=[r[1] for r in self.conn.execute('PRAGMA table_info('+identifier(name)+')')]
            self.conn.executemany('INSERT INTO '+identifier(name)+' VALUES ('+','.join('?' for _ in fields)+')',
                [tuple(r.get(f) for f in fields) for r in self.records[name]])
        self.conn.commit();self.conn.execute('DETACH DATABASE original')
        self.client=TestClient(app,base_url='https://testserver')
        self.headers={'x-forwarded-access-token':'app-subset-viewer'}
        self.queries=[]

    def tearDown(self):self.conn.close()

    def warehouse(self,sql,params,user):
        with self.query_lock:return self._warehouse_read(sql,params,user)

    def _warehouse_read(self,sql,params,user):
        self.queries.append(sql)
        if '.information_schema.columns ' in sql:
            if 'column_name AS name' in sql:
                self.assertEqual(params['schema'],'app_gold')
                return [{'name':r['name'],'type':r['type']} for r in self.conn.execute('PRAGMA table_info('+identifier(params['name'])+')')]
            self.assertEqual(params['schema0'],'app_gold')
            if store.shared_data:self.assertEqual({v for k,v in params.items() if k.startswith('table')},set(publisher.TABLES))
            else:self.assertEqual(set(params.values()),{'app_gold'})
            return [{'table_catalog':'source-data','table_schema':'app_gold','table_name':n,
                     'column_name':r['name'],'full_data_type':r['type']} for n in publisher.TABLES
                    for r in self.conn.execute('PRAGMA table_info('+identifier(n)+')')]
        self.assertNotIn('`media-poc`.`gold`',sql)
        translated=sql.replace('`source-data`.`app_gold`.','').replace(' AS STRING)',' AS TEXT)')
        try:return [dict(r) for r in self.conn.execute(translated,params)]
        except sqlite3.Error as error:raise DataError(str(error)) from error

    def test_only_30_tables_support_all_pages_filters_exports_and_narrowed_schema_browser(self):
        baseline_client=TestClient(app)
        with patch.object(store,'mode','preview'):
            baseline={page:baseline_client.get('/api/dashboard/'+page).json() for page in PAGES}
        with patch.object(store,'mode','live'),patch.object(store,'query',side_effect=self.warehouse):
            response=self.client.post('/api/connection',json={'gold_catalog':'source-data','gold_schema':'app_gold'},headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['verified_source_objects'],{'gold':30})
            result=self.client.get('/api/bootstrap',headers=self.headers)
            self.assertEqual(result.status_code,200,result.text)
            bootstrap=result.json()
            self.assertEqual(len(bootstrap['tables']),30)
            self.assertEqual({r['name'] for r in bootstrap['tables']},set(publisher.TABLES))
            self.assertEqual(bootstrap['sources'],len(self.records['gold_source_coverage']))
            names={r['campaign_key']:r['campaign_name'] for r in bootstrap['campaigns']}
            self.assertEqual(names['CMP001'],'Everyday Checking - Regional Acquisition')
            for page in PAGES:
                result=self.client.get('/api/dashboard/'+page,headers=self.headers)
                self.assertEqual(result.status_code,200,result.text)
                self.assertFalse(any(m['unavailable_reason'] for m in result.json()['metrics']))
                self.assertTrue(all(c['rows'] and not c.get('unavailable_reason') for c in result.json()['charts']))
                self.assertTrue(all(m['source'].startswith('source-data.app_gold.') for m in result.json()['metrics']))
                self.assertEqual([m['value'] for m in result.json()['metrics']],
                                 [m['value'] for m in baseline[page]['metrics']])
                self.assertEqual([c['rows'] for c in result.json()['charts']],
                                 [c['rows'] for c in baseline[page]['charts']])
                if page=='overview':self.assertEqual(result.json()['metrics'][2]['value'],282)
            filtered=self.client.get('/api/dashboard/overview?campaign=CMP001&platform=meta',headers=self.headers).json()
            self.assertEqual(filtered['metrics'][1]['value'],93)
            self.assertIsNone(filtered['metrics'][2]['value'])
            for endpoint in ['table','schema','export']:
                result=self.client.get('/api/'+endpoint+'/mart_vendor_media_daily',headers=self.headers)
                self.assertEqual(result.status_code,200,result.text)
            for kind in ['lineage','metrics','readiness']:
                self.assertEqual(self.client.get('/api/metadata/'+kind,headers=self.headers).status_code,200)
            result=self.client.get('/api/workspace-schema',headers=self.headers)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(len(result.json()['tables']),30)
            self.assertEqual(self.client.get('/api/table/dim_customer',headers=self.headers).status_code,404)
        self.assertFalse(any('`usecases`' in sql or '`use_cases`' in sql for sql in self.queries))


if __name__=='__main__':unittest.main()
