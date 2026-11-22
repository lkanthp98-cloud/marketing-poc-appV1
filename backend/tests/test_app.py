"""Reporting, filter isolation and SQL access contract checks against supplied POC data."""
import csv
import io
import os
import json
import re
import sqlite3
import unittest
from unittest.mock import patch

os.environ["DATA_MODE"] = "preview"
from fastapi.testclient import TestClient
from backend.main import app, previous_period, store
from backend.store import ACTIVE_CONNECTION, ANALYTICS_MAPPING, WORKSPACE_CONTRACT, DataError, Store, Viewer, identifier, preview_database


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def get(self, url, **params):
        response = self.client.get(url, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_inventory_preserves_all_feeds_and_entities(self):
        result = self.get('/api/bootstrap')
        self.assertEqual(result['sources'], 91)
        self.assertEqual(len(result['tables']), 113)
        self.assertEqual(sum(t['kind'] == 'mart' for t in result['tables']), 29)
        self.assertEqual(result['dates'], {'start': '2026-04-01', 'end': '2026-11-01'})
        self.assertEqual(result['mode'], 'preview')

    def test_every_page_executes_every_chart(self):
        for page in ['overview', 'campaigns', 'acquisition', 'digital', 'finance', 'experiments']:
            with self.subTest(page=page):
                data = self.get('/api/dashboard/' + page)
                self.assertEqual(len(data['metrics']), 4)
                self.assertEqual(len(data['charts']), 3)
                self.assertTrue(all(chart['rows'] for chart in data['charts']))

    def test_source_totals_and_weighted_rates(self):
        data = self.get('/api/dashboard/campaigns')['metrics']
        self.assertAlmostEqual(data[0]['value'], 790179.109988, places=5)
        self.assertEqual(data[1]['value'], 56797673)
        self.assertAlmostEqual(data[2]['value'], 1729617 / 56797673)
        self.assertAlmostEqual(data[3]['value'], 790179.109988 / 1729617)
        overview = self.get('/api/dashboard/overview')['metrics']
        self.assertEqual(overview[2]['value'], 282)
        self.assertAlmostEqual(overview[3]['value'], 105265.94)

    def test_experiment_counts_and_uncertainty(self):
        result = self.get('/api/dashboard/experiments')
        self.assertEqual([r['value'] for r in result['metrics'][:2]], [480, 81])
        comparison = result['charts'][1]['rows'][0]
        self.assertAlmostEqual(comparison['effect'], 1 / 240)
        self.assertLess(comparison['lower'], 0)
        self.assertGreater(comparison['upper'], 0)

    def test_platform_filter_reconciles_to_chart_total(self):
        unfiltered = self.get('/api/dashboard/campaigns')
        platform = unfiltered['charts'][0]['rows'][0]
        filtered = self.get('/api/dashboard/campaigns', platform=platform['label'])
        self.assertAlmostEqual(filtered['metrics'][0]['value'], platform['spend'])
        self.assertEqual(len(filtered['charts'][0]['rows']), 1)

    def test_enterprise_campaign_filter_does_not_guess_unapproved_vendor_mappings(self):
        result = self.get('/api/dashboard/overview', campaign='CMP001')
        self.assertIsNone(result['metrics'][0]['value'])
        self.assertGreater(result['metrics'][1]['value'], 0)

    def test_currency_is_filtered_without_summing_native_currencies(self):
        result = self.get('/api/dashboard/overview', currency='CAD')
        self.assertIsNone(result['metrics'][0]['value'])
        self.assertIsNone(result['metrics'][3]['value'])

    def test_monthly_comparison_uses_nonoverlapping_whole_months(self):
        self.assertEqual(previous_period({'start': '2026-05-15', 'end': '2026-05-31'}, monthly=True),
                         {'start': '2026-04-01', 'end': '2026-04-30'})
        self.assertEqual(previous_period({'start': '2026-01-15', 'end': '2026-02-28'}, monthly=True),
                         {'start': '2025-11-01', 'end': '2025-12-31'})
        data = self.get('/api/dashboard/experiments', start='2026-05-01', end='2026-05-31', compare=True)
        self.assertIsNone(data['metrics'][0]['change'])

    def test_plan_version_is_single_and_actuals_are_not_duplicated(self):
        data = self.get('/api/dashboard/finance')
        self.assertAlmostEqual(data['metrics'][3]['value'], 0.18070554355651547)

    def test_pagination_sort_and_export_search_agree(self):
        first = self.get('/api/table/mart_vendor_media_daily', size=20, sort='spend_amount')
        second = self.get('/api/table/mart_vendor_media_daily', size=20, page=1, sort='spend_amount')
        self.assertEqual(len(first['rows']), 20)
        self.assertGreaterEqual(first['rows'][0]['spend_amount'], second['rows'][0]['spend_amount'])
        selected = self.get('/api/table/mart_vendor_media_daily', search='youtube', size=100)
        response = self.client.get('/api/export/mart_vendor_media_daily', params={'search': 'youtube'})
        records = list(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(len(records), selected['total'])
        self.assertTrue(all('youtube' in str(row).lower() for row in records))

    def test_bad_filters_and_sql_identifiers_are_rejected(self):
        cases = [('/api/dashboard/overview?start=no-date', 400),
                 ('/api/dashboard/overview?start=2026-09-01&end=2026-01-01', 400),
                 ('/api/table/dim_campaign?size=10001', 422),
                 ('/api/table/dim_campaign?sort=campaign_key;DROP%20TABLE%20x', 400),
                 ('/api/table/not_a_published_table', 404), ('/api/dashboard/missing', 404)]
        for url, code in cases:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, code)
        self.assertEqual(self.get('/api/table/dim_campaign', search="' OR 1=1 --")['total'], 0)
        with self.assertRaises(DataError):
            identifier('x; DROP TABLE y')

    def test_all_catalog_tables_and_metadata_are_readable(self):
        for item in self.get('/api/bootstrap')['tables']:
            with self.subTest(table=item['name']):
                self.get('/api/table/' + item['name'], size=1)
        self.assertEqual(len(self.get('/api/metadata/lineage')), 91)
        self.assertEqual(len(self.get('/api/metadata/readiness')), 10)
        self.assertTrue(self.get('/api/metadata/metrics'))

    def test_exported_use_case_location_inventory_and_full_data_are_accessible(self):
        bootstrap=self.get('/api/bootstrap')
        self.assertEqual((bootstrap['analytics_catalog'],bootstrap['analytics_schema']),('source-data','usecases'))
        self.assertEqual(len(bootstrap['use_case_tables']),30)
        self.assertEqual(sum(t['kind']=='mart' for t in bootstrap['use_case_tables']),28)
        for item in bootstrap['use_case_tables']:
            with self.subTest(table=item['name']):
                data=self.get('/api/table/'+item['name'],layer='use_cases',size=1)
                self.assertEqual(data['source'],'source-data.usecases.'+item['name'])
        result=self.get('/api/dashboard/campaigns')
        self.assertTrue(all(metric['table'] in ANALYTICS_MAPPING.values() for metric in result['metrics']))
        self.assertTrue(all(chart['source'].startswith('source-data.usecases.') for chart in result['charts']))

    def test_use_case_schema_does_not_read_data_and_contains_publication_columns(self):
        with patch.object(store,'query',wraps=store.query) as query:
            data=self.get('/api/schema/uc02_vendor_media_daily',layer='use_cases')
        self.assertIn('_uc_publication_id',{c['name'] for c in data['schema']})
        self.assertFalse(any('SELECT * FROM `uc02_vendor_media_daily`' in call.args[0] for call in query.call_args_list))
        self.assertEqual(data['source'],'source-data.usecases.uc02_vendor_media_daily')
        self.assertEqual(self.client.get('/api/table/uc02_vendor_media_daily').status_code,404)
        self.assertEqual(self.client.get('/api/table/mart_vendor_media_daily',params={'layer':'use_cases'}).status_code,404)

    def test_use_case_export_filters_preserve_source_rows_and_provenance(self):
        data=self.get('/api/table/uc02_vendor_media_daily',layer='use_cases',search='youtube',size=100)
        response=self.client.get('/api/export/uc02_vendor_media_daily',params={'layer':'use_cases','search':'youtube'})
        records=list(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(len(records),data['total'])
        self.assertTrue(all(row['_uc_publication_id']=='local-preview' for row in records))

    def test_mocked_live_namespace_routing_keeps_business_marts_in_use_cases(self):
        captured=[]
        contract=WORKSPACE_CONTRACT['tables']
        def simulated_warehouse(sql,params,user):
            captured.append(sql)
            if '.information_schema.columns ' in sql:
                catalog='source-data' if '`source-data`' in sql else 'media-poc'
                exported=contract[catalog+'.'+params['schema']+'.'+params['name']]['columns']
                # The local source-derived fixture simplifies ancillary attributes. This stand-in
                # tests namespace routing; all dashboard fields are separately checked against CSVs.
                connection=sqlite3.connect(preview_database())
                try: present={row[1] for row in connection.execute('PRAGMA table_info('+identifier(params['name'])+')')}
                finally: connection.close()
                return [column for column in exported if column['name'] in present]
            sql=re.sub(r'`(?:media-poc|source-data)`\.`(?:gold|usecases)`\.', '', sql)
            sql=sql.replace(' AS STRING)',' AS TEXT)')
            connection=sqlite3.connect(preview_database()); connection.row_factory=sqlite3.Row
            try:return [dict(row) for row in connection.execute(sql,params).fetchall()]
            finally:connection.close()
        with patch.object(store,'mode','live'),patch.object(store,'query',side_effect=simulated_warehouse):
            headers={'x-forwarded-access-token':'mock-user'}
            for page in ['overview','campaigns','acquisition','digital','finance','experiments']:
                response=self.client.get('/api/dashboard/'+page,headers=headers)
                self.assertEqual(response.status_code,200,response.text)
            self.assertFalse(any(re.search(r'FROM `media-poc`\.`gold`\.`mart_',sql) for sql in captured))
            self.assertTrue(any('`source-data`.`usecases`.`uc02_vendor_media_daily`' in sql for sql in captured))
            captured.clear()
            response=self.client.get('/api/table/mart_vendor_media_daily?layer=gold&size=1',headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(any('FROM `media-poc`.`gold`.`mart_vendor_media_daily`' in sql for sql in captured))

    def test_all_five_uploaded_schema_exports_remain_associated_with_their_columns(self):
        data=self.get('/api/workspace-schema')
        self.assertEqual(data['verification'],'UPLOADED_SCHEMA_REFERENCE')
        self.assertEqual(len(data['tables']),407)
        self.assertEqual(sum(len(t['columns']) for t in data['tables']),5315)
        self.assertEqual({(t['catalog'],t['schema']) for t in data['tables']},
            {('media-poc',s) for s in ['bronze','silver','model','gold']}|{('source-data','usecases')})
        table=next(t for t in data['tables'] if t['name']=='uc02_vendor_media_daily')
        self.assertIn({'name':'spend_amount','type':'DECIMAL'},table['columns'])

    def test_preview_connection_cannot_claim_a_live_connection(self):
        profile=self.get('/api/connection')['connection']
        response=self.client.post('/api/connection',json=profile)
        self.assertEqual(response.status_code,400)
        self.assertIn('Sample mode',response.text)

    def test_live_connection_is_validated_saved_and_isolated_per_browser(self):
        original=store.query; seen=[]
        profile={'gold_catalog':'alternate','gold_schema':'analytics_gold','use_cases_catalog':'reporting','use_cases_schema':'marketing_usecases'}
        def warehouse(sql,params,user):
            seen.append(sql)
            if 'SELECT table_name, column_name' in sql:
                return [{'table_name':t['name'],'column_name':c['name']} for t in WORKSPACE_CONTRACT['tables'].values()
                    if t['schema']=='usecases' for c in t['columns']]
            if '.information_schema.columns ' in sql:
                prefix='source-data.usecases.' if params['schema']=='marketing_usecases' else 'media-poc.gold.'
                return WORKSPACE_CONTRACT['tables'][prefix+params['name']]['columns']
            translated=re.sub(r'`(?:alternate|reporting)`\.`(?:analytics_gold|marketing_usecases)`\.','',sql)
            connection=sqlite3.connect(preview_database()); connection.row_factory=sqlite3.Row
            try:rows=[dict(row) for row in connection.execute(translated,params).fetchall()]
            finally:connection.close()
            if 'use_case_dataset_catalog' in sql:
                for row in rows:row['source_gold_table']=row['source_gold_table'].replace('`media-poc`.`gold`','`alternate`.`analytics_gold`')
            return rows
        client=TestClient(app,base_url='https://testserver')
        headers={'x-forwarded-access-token':'browser-one'}
        with patch.object(store,'mode','live'),patch.object(store,'query',side_effect=warehouse):
            response=client.post('/api/connection',json=profile,headers=headers)
            self.assertEqual(response.status_code,200,response.text)
            self.assertIn('Secure',response.headers['set-cookie'])
            saved=client.get('/api/connection',headers=headers).json()
            self.assertEqual(saved['connection'],{**profile,'source_mode':'both'})
            # Dashboard worker threads inherit this browser's request context.
            seen.clear(); result=client.get('/api/dashboard/campaigns',headers=headers)
            self.assertEqual(result.status_code,200,result.text)
            self.assertTrue(any('`reporting`.`marketing_usecases`.`uc02_vendor_media_daily`' in sql for sql in seen))
            other=TestClient(app,base_url='https://testserver')
            default=other.get('/api/connection',headers={'x-forwarded-access-token':'browser-two'}).json()['connection']
            self.assertEqual(default['gold_catalog'],'media-poc')
            self.assertEqual(ACTIVE_CONNECTION.get(),{})

    def test_live_schema_browser_uses_authorized_metadata_not_uploaded_static_data(self):
        rows=[{'table_catalog':'media-poc','table_schema':'gold','table_name':'dim_campaign','column_name':'campaign_key','full_data_type':'STRING'}]
        with patch.object(store,'mode','live'),patch.object(store,'query',return_value=rows) as query:
            response=self.client.get('/api/workspace-schema',headers={'x-forwarded-access-token':'schema-viewer'})
        data=response.json()
        self.assertEqual(data['verification'],'LIVE_AUTHORIZED_INFORMATION_SCHEMA')
        self.assertEqual(len(data['tables']),1)
        self.assertTrue(all('.information_schema.columns ' in call.args[0] for call in query.call_args_list))

    def test_live_mode_requires_viewer_token_and_never_serves_preview(self):
        with patch.object(store, 'mode', 'live'):
            response = self.client.get('/api/bootstrap')
            self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.get('/api/bootstrap').headers['Cache-Control'], 'no-store')


class WarehouseTests(unittest.TestCase):
    def test_scope_and_viewer_both_isolate_column_cache(self):
        warehouse=Store(); warehouse.mode='live'
        with patch.object(warehouse,'query',return_value=[{'name':'report_date','type':'DATE'}]) as query:
            warehouse.columns('mart_vendor_media_daily',Viewer('one'),'gold')
            warehouse.columns('mart_vendor_media_daily',Viewer('one'),'use_cases')
            warehouse.columns('mart_vendor_media_daily',Viewer('one'),'gold')
            warehouse.columns('mart_vendor_media_daily',Viewer('two'),'use_cases')
        self.assertEqual(query.call_count,3)
        locations=[call.args[1] for call in query.call_args_list]
        self.assertEqual(locations[0],{'schema':'gold','name':'mart_vendor_media_daily'})
        self.assertEqual(locations[1],{'schema':'usecases','name':'uc02_vendor_media_daily'})

    def test_sql_api_parameter_binding_chunking_and_types(self):
        warehouse = Store()
        warehouse.mode = 'live'
        responses = [
            {'statement_id': 'abc', 'status': {'state': 'SUCCEEDED'},
             'manifest': {'schema': {'columns': [{'name': 'amount', 'type_name': 'DECIMAL'}]}},
             'result': {'data_array': [['10.25']], 'next_chunk_internal_link': '/api/2.0/sql/statements/abc/result/chunks/1'}},
            {'data_array': [['20.75']]},
        ]
        with patch.object(warehouse, '_request', side_effect=responses) as request:
            rows = warehouse.query('SELECT amount WHERE campaign=:campaign', {'campaign': "'unsafe"}, Viewer('secret'))
        self.assertEqual(rows, [{'amount': 10.25}, {'amount': 20.75}])
        body = request.call_args_list[0].args[2]
        self.assertNotIn("'unsafe", body['statement'])
        self.assertEqual(body['parameters'], [{'name': 'campaign', 'type': 'STRING', 'value': "'unsafe"}])

    def test_failed_live_query_has_no_preview_fallback(self):
        warehouse = Store()
        warehouse.mode = 'live'
        with patch.object(warehouse, '_request', return_value={'statement_id': 'abc', 'status': {'state': 'FAILED'}}):
            with self.assertRaises(DataError):
                warehouse.query('SELECT 1', {}, Viewer('viewer'))

    def test_schema_cache_is_scoped_to_viewer_identity(self):
        warehouse = Store()
        warehouse.mode = 'live'
        with patch.object(warehouse, 'query', return_value=[{'name': 'id', 'type': 'STRING'}]) as query:
            warehouse.columns('dim_campaign', Viewer('first'))
            warehouse.columns('dim_campaign', Viewer('first'))
            warehouse.columns('dim_campaign', Viewer('second'))
        self.assertEqual(query.call_count, 2)


if __name__ == '__main__':
    unittest.main()
