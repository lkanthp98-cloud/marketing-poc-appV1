"""Regression checks for campaign identity, Gold lineage and honest filter scope."""
import itertools
import re
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app, store, campaign_options
from backend.store import Viewer
from backend.store import WORKSPACE_CONTRACT
from backend.catalog import PAGES


class GoldFilterTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(app)

    def test_name_resolution_is_order_independent_and_never_overwritten_by_an_id(self):
        records=[{'campaign_key':'CMP001','campaign_name':'Everyday Checking','master':True},
                 {'campaign_key':'CMP001','campaign_name':'CMP001'},
                 {'campaign_key':'CMP001','campaign_name':None}]
        for rows in itertools.permutations(records):
            self.assertEqual(campaign_options(rows,[]),[{'campaign_key':'CMP001','campaign_name':'Everyday Checking'}])

    def test_master_name_wins_and_conflicts_or_missing_names_are_explicit(self):
        warnings=[]
        result=campaign_options([
            {'campaign_key':'A','campaign_name':'Master','master':True},
            {'campaign_key':'A','campaign_name':'Stale mart label'},
            {'campaign_key':'B','campaign_name':'unknown'},
            {'campaign_key':'C','campaign_name':'First','master':True},
            {'campaign_key':'C','campaign_name':'Second','master':True}],warnings)
        names={r['campaign_key']:r['campaign_name'] for r in result}
        self.assertEqual(names['A'],'Master')
        self.assertEqual(names['B'],'Name unavailable (B)')
        self.assertEqual(names['C'],'Conflicting campaign names (C)')
        self.assertEqual(len(warnings),3)

    def test_filter_labels_are_real_names_and_values_remain_enterprise_ids(self):
        response=self.client.get('/api/bootstrap').json()
        names={r['campaign_key']:r['campaign_name'] for r in response['campaigns']}
        self.assertEqual(names['CMP001'],'Everyday Checking - Regional Acquisition')
        self.assertEqual(names['CMP006'],'Small Business Banking Growth')

    def test_every_dashboard_expression_and_dimension_is_in_the_gold_export(self):
        checked=0
        for page,spec in PAGES.items():
            elements=[(m.table,[m.expression],[]) for m in spec['metrics']]
            elements += [(c.table,[m['expression'] for m in c.measures],c.dimensions) for c in spec['charts']]
            for table,expressions,dimensions in elements:
                required=set(dimensions)
                for expression in expressions:
                    required.update(re.findall(r'`([^`]+)`',expression))
                    if re.fullmatch(r'[a-z][a-z0-9_]*',expression):required.add(expression)
                columns={c['name'] for c in WORKSPACE_CONTRACT['tables']['media-poc.gold.'+table]['columns']}
                self.assertFalse(required-columns,(page,table,required-columns))
                checked+=1
        self.assertEqual(checked,42)

    def test_selected_campaign_and_platform_match_exact_gold_rows(self):
        expected=store.query('SELECT SUM(crm_leads) AS leads FROM mart_demo_campaign_economics '
            'WHERE campaign_key=:campaign AND platform=:platform',{'campaign':'CMP001','platform':'meta'},Viewer())[0]['leads']
        response=self.client.get('/api/dashboard/overview?campaign=CMP001&platform=meta').json()
        self.assertEqual(response['metrics'][1]['value'],expected)
        self.assertIsNone(response['metrics'][2]['value'])
        self.assertIn('published Gold grain',response['metrics'][2]['unavailable_reason'])
        self.assertIsNone(response['metrics'][3]['value'])
        self.assertEqual(self.client.get('/api/dashboard/overview').json()['metrics'][2]['value'],282)

    def test_offline_channel_is_not_treated_as_an_ad_platform(self):
        response=self.client.get('/api/dashboard/digital?platform=meta').json()
        for item in response['metrics']:
            self.assertIsNone(item['value'])
            self.assertIn('platform',item['unavailable_reason'])

    def test_platform_options_include_gold_demo_platforms_absent_from_vendor_rows(self):
        original=store.query
        def query(sql,params,user):
            if 'SELECT DISTINCT `platform` AS value FROM `mart_demo_paid_media_daily`' in sql:
                return [{'value':'demo_only_platform'}]
            return original(sql,params,user)
        with patch.object(store,'query',side_effect=query):
            self.assertIn('demo_only_platform',self.client.get('/api/bootstrap').json()['platforms'])


if __name__=='__main__':unittest.main()
