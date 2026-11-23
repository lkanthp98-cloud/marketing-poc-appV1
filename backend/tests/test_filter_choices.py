"""Verify live option loading, partial failures, and grain-aware advanced filters."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app,store,FILTER_SOURCES
from backend.store import DataError


class FilterChoiceTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(app)

    def test_actual_options_and_status_are_available_for_every_marked_control(self):
        result=self.client.get('/api/bootstrap').json()
        for key in FILTER_SOURCES:
            self.assertTrue(result[key],key)
            self.assertEqual(result['filter_status'][key]['state'],'available')
        self.assertIn('meta',result['platforms']);self.assertIn('USD',result['currencies'])

    def test_failed_platform_sources_use_other_gold_choices_and_report_failure(self):
        original=store.query
        def query(sql,params,user):
            if 'CAST(`platform` AS STRING) AS value' in sql and any('FROM `'+n+'`' in sql for n in ['mart_vendor_media_daily','mart_demo_paid_media_daily']):
                raise DataError('Simulated access failure',403)
            return original(sql,params,user)
        with patch.object(store,'query',side_effect=query):result=self.client.get('/api/bootstrap').json()
        self.assertIn('meta',result['platforms'])
        self.assertTrue(result['filter_status']['platforms']['errors'])
        self.assertTrue(any('Simulated access failure' in warning for warning in result['warnings']))

    def test_failed_option_queries_are_not_presented_as_empty_success(self):
        original=store.query
        def query(sql,params,user):
            if 'CAST(`currency` AS STRING) AS value' in sql or 'CAST(`plan_version` AS STRING) AS value' in sql:
                raise DataError('Simulated warehouse failure',503)
            return original(sql,params,user)
        with patch.object(store,'query',side_effect=query):result=self.client.get('/api/bootstrap').json()
        for key in ['currencies','plans']:
            self.assertEqual(result[key],[])
            self.assertEqual(result['filter_status'][key]['state'],'unavailable')
            self.assertIn('Refresh data',result['filter_status'][key]['message'])

    def test_product_and_market_filters_reconcile_and_never_leave_unrelated_totals(self):
        choices=self.client.get('/api/bootstrap').json()
        for key,options in [('product',choices['products']),('market',choices['markets'])]:
            value=next(v for v in options if v.lower()!='unknown')
            filtered=self.client.get('/api/dashboard/overview',params={key:value}).json()
            self.assertIsNone(filtered['metrics'][0]['value'])
            self.assertIn(key,filtered['metrics'][0]['unavailable_reason'])
            field='product_id' if key=='product' else 'market_id'
            expected=store.query('SELECT SUM(funded_accounts) AS n FROM mart_banking_funded_accounts_monthly WHERE '+field+'=:value',
                                 {'value':value},None)[0]['n']
            self.assertEqual(filtered['metrics'][2]['value'],expected)

    def test_explicit_plan_version_is_used_without_duplicating_actuals(self):
        choices=self.client.get('/api/bootstrap').json()
        for plan in choices['plans']:
            result=self.client.get('/api/dashboard/finance',params={'plan':plan}).json()
            expected=store.query('SELECT 1.0*SUM(funded_accounts)/NULLIF(SUM(target_funded_accounts),0) AS n '
                'FROM mart_sales_target_attainment_monthly WHERE plan_version=:plan',{'plan':plan},None)[0]['n']
            self.assertEqual(result['metrics'][3]['value'],expected)


if __name__=='__main__':unittest.main()
