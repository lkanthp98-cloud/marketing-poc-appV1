"""Build a local, explicitly labeled preview from this POC's source CSVs.

Run from the app directory. Production always queries published Databricks Gold.
"""

import ast
import datetime as dt
import gzip
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import NormalDist


APP = Path(__file__).resolve().parents[1]
WORKSPACE = APP.parent
sys.path.insert(0, str(WORKSPACE / "tests"))
from test_pipeline_contracts import selected_csv_records


def code(name):
    return {c["id"]: "".join(c["source"]) for c in json.loads((WORKSPACE / name).read_text(encoding="utf-8"))["cells"]
            if c["cell_type"] == "code"}


def literal(source, key):
    return next(ast.literal_eval(node.value) for node in ast.parse(source).body if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == key for t in node.targets))


def clean(value):
    return value if value is not None and str(value).strip().lower() not in {"", "unknown"} else None


def system(value):
    value = str(value).lower() if clean(value) else None
    return {"programmatic": "dsp", "snap": "snapchat", "website": "website_experiment", "tv": "broadcast_tv"}.get(value, value)


def token(value, channel):
    if not clean(value):
        return None
    value = str(value).strip().upper()
    return value.replace("_", "-") if channel == "website_experiment" else value


def month(value):
    return str(value)[:7] + "-01" if value else None


def number(value):
    return float(value or 0)


def ratio(a, b):
    return float(a) / float(b) if b else None


def json_default(value):
    return float(value) if isinstance(value, Decimal) else str(value)


def group(rows, keys):
    result = defaultdict(list)
    for row in rows:
        result[tuple(row.get(key) for key in keys)].append(row)
    return result


def roll(rows, keys, sums=(), counts=None):
    output = []
    for values, records in group(rows, keys).items():
        row = dict(zip(keys, values))
        row.update({field: sum(number(record.get(field)) for record in records) for field in sums})
        for label, predicate in (counts or {}).items():
            row[label] = sum(bool(predicate(record)) for record in records)
        output.append(row)
    return output


def read_pass_records(dqx):
    scope = {}
    exec(dqx["silver-schema"], scope)
    exec(dqx["rule-specification"], scope)
    inputs = selected_csv_records(scope["SILVER_SCHEMA"])
    passed = {}
    for table, rows in inputs.items():
        keys = scope["KEYS"].get(table, "").split()
        key = lambda row: tuple(row[field] for field in keys)
        unique = {tuple(row.items()): row for row in rows}
        counts = Counter(key(row) for row in unique.values())
        refs = [(field, {row[field] for row in inputs[parent]}, required)
                for field, parent, required in scope["REFERENCES"].get(table, [])]
        accepted = []
        for row in unique.values():
            if keys and (not all(clean(value) is not None for value in key(row)) or counts[key(row)] > 1):
                continue
            if any((required and clean(row[field]) is None) or (clean(row[field]) is not None and row[field] not in allowed)
                   for field, allowed, required in refs):
                continue
            if any(row[field] < 0 for field in scope["NONNEGATIVE"].get(table, [])):
                continue
            if table == "ecom_order_items" and row["quantity"] <= 0:
                continue
            if table == "extra_reference_fx_rates_daily" and row["rate"] <= 0:
                continue
            if any(row.get(start) and row.get(end) and row[start] > row[end] for start, end in scope["DATE_RANGES"]):
                continue
            accepted.append(row)
        passed[table] = accepted
    assert sum(map(len, passed.values())) == 68372
    return scope, passed


def build_entities(spec, inputs):
    crosswalk = {(system(row["source_system"]), token(row["source_campaign_id"], system(row["source_system"]))): row
                 for row in inputs["campaign_crosswalk"]}
    customer_ids = {row["customer_id"] for row in inputs["reference_customer_master_export"]}

    def campaign_fields(channel, native):
        channel = system(channel)
        match = token(native, channel)
        candidate = crosswalk.get((channel, match))
        state = "missing_source_campaign_id" if match is None else "unmapped"
        if candidate:
            state = "demo_only" if candidate["mapping_status"] == "DEMO_APPROVED" else "review_required"
        return dict(mapping_source_system=channel, campaign_match_token=match, mapping_source_campaign_id=clean(native),
                    resolved_campaign_key=None, proposed_campaign_key=candidate["proposed_campaign_key"] if candidate else None,
                    campaign_resolution_status=state)

    models = {}
    for name, (table, keys) in spec["NATIVE"].items():
        records = []
        for raw in inputs[table]:
            row = raw.copy()
            if name in spec["CAMPAIGN_REFS"]:
                channel, field = spec["CAMPAIGN_REFS"][name]
                row.update(campaign_fields(row[channel[1:]] if channel.startswith("@") else channel, row[field]))
            if name in spec["CUSTOMER_REFS"]:
                row["modeled_customer_id"] = row["customer_id"] if row["customer_id"] in customer_ids else None
                row["customer_resolution_status"] = "verified_by_crosswalk" if row["modeled_customer_id"] else "unresolved"
            if name == "dim_campaign":
                row.update(campaign_name=row["campaign_title"], campaign_start_date=row["start_dt"], campaign_end_date=row["end_dt"])
            records.append(row)
        models[name] = records

    setups = {row["source_campaign_id"]: row for row in models["dim_paid_source_campaign"]}
    models["dim_paid_ad"] = [{**row, **{key: setups[row["source_campaign_id"]][key] for key in
                                ("platform", "campaign_key", "resolved_campaign_key", "campaign_resolution_status")}}
                             for row in inputs["paid_ad_catalog"]]
    ads = {row["ad_id"]: row for row in models["dim_paid_ad"]}
    for name, table in (("fact_paid_ad_delivery_daily", "paid_ad_delivery_daily"), ("fact_paid_submission", "paid_form_and_outcome_links")):
        models[name] = [{**row, **{key: ads[row["ad_id"]][key] for key in
                         ("source_campaign_id", "platform", "campaign_key", "resolved_campaign_key", "campaign_resolution_status", "market_id", "format")}}
                        for row in inputs[table]]
    models["dim_web_experiment_variant"] = [{**row, "variant_id": row["variant"].split("/")[0].strip(),
                                             **campaign_fields("website_experiment", row["cmpgn_ref"])}
                                            for row in inputs["website_experiment_ab_test_configuration_export"]]
    models["audit_campaign_crosswalk"] = inputs["campaign_crosswalk"]
    models["bridge_campaign_source"] = [{**row, **campaign_fields(row["source_system"], row["source_campaign_id"]),
                                          "resolution_status": "demo_only" if row["mapping_status"] == "DEMO_APPROVED" else "review_required"}
                                         for row in inputs["campaign_crosswalk"]]
    models["bridge_customer_source"] = [{**row, "mapped_source_system": row["source_system"], "resolved_customer_id": row["customer_id"]}
                                         for row in inputs["reference_customer_source_id_crosswalk"]]
    models["bridge_campaign_approved"] = []
    models["campaign_resolution_candidates"] = [dict(source_system=row["source_system"].upper(), source_campaign_id=row["source_campaign_id"],
        canonical_system=system(row["source_system"]).upper(), canonical_campaign_id=token(row["source_campaign_id"], system(row["source_system"])),
        campaign_key=row["proposed_campaign_key"], candidate_sources="DQ_CROSSWALK", evidence=row["evidence"],
        technical_validation="CANDIDATE_VALIDATED", enterprise_candidate_count=1)
        for row in inputs["campaign_crosswalk"] if row["mapping_status"] != "DEMO_APPROVED"]
    vendor = []
    for platform, table, start, end, campaign, title, breakdown, impressions, clicks, event, spend, currency, conversions, conversion_event, value, reach in spec["VENDORS"]:
        for row in inputs[table]:
            amount = number(row[spend]) / (1000000 if spend.endswith(("_micro", "_micros")) else 1)
            conversion_label = row[conversion_event[1:]] if conversion_event.startswith("@") else conversion_event
            vendor.append(dict(source_table=table, platform=platform, report_date=row[start], report_end_date=row[end or start],
                source_campaign_id=row[campaign], source_campaign_name=row[title], breakdown_key=json.dumps([row[x] for x in breakdown.split()]),
                reported_impressions=row[impressions], reported_clicks=row[clicks], click_event=event, spend_amount=round(amount, 6),
                currency=currency[1:] if currency.startswith("=") else row[currency], reported_conversions=row[conversions],
                conversion_event=conversion_label, reported_conversion_value=row[value] if value else None,
                conversion_value_event="purchase" if platform == "meta" else conversion_label if value else None,
                reported_reach=row[reach] if reach else None, source_record_json=json.dumps(row, default=json_default),
                **campaign_fields(platform, row[campaign])))
    models["fact_vendor_delivery"] = vendor
    models["dim_vendor_campaign"] = []
    for platform, table, native, title, start, end, status, amount, currency, period in spec["VENDOR_SETUP"]:
        for row in inputs[table]:
            campaign = row[native].split("/")[-1] if platform == "google_ads" else row[native]
            models["dim_vendor_campaign"].append(dict(platform=platform, source_campaign_id=campaign, source_campaign_name=row[title],
                flight_start=row[start], flight_end=row[end], campaign_status=row[status],
                budget_amount=number(row[amount]) / (1000000 if amount.endswith("_micros") else 1),
                currency=row[currency].upper() if currency else None, budget_period=row[period[1:]].lower() if period.startswith("@") else period or None,
                source_record_json=json.dumps(row, default=json_default), **campaign_fields(platform, campaign)))
    ledger = defaultdict(float)
    for row in inputs["demo_marketing_gl"]:
        ledger[row["finance_link_id"], row["currency"]] += number(row["debit_usd"]) - number(row["credit_usd"])
    models["fact_demo_finance_reconciliation"] = [{**row, "invoice_net_usd": row["net_invoice_usd"],
        "gl_net_usd": ledger[row["finance_link_id"], row["currency"]],
        "invoice_minus_gl_usd": round(number(row["net_invoice_usd"]) - ledger[row["finance_link_id"], row["currency"]], 2),
        "reconciliation_status": "matched"} for row in inputs["demo_media_invoices"]]
    model_dates = sorted({value for table, records in inputs.items() for row in records for key, value in row.items()
                          if value and isinstance(value, str) and len(value) == 10 and value[4:5] == "-" and value[7:8] == "-"})
    holidays = {row["holiday_date"]: row for row in inputs["extra_reference_us_holiday_calendar"]}
    day = dt.date.fromisoformat(model_dates[0])
    last = dt.date.fromisoformat(model_dates[-1])
    models["dim_date"] = []
    while day <= last:
        date = day.isoformat()
        models["dim_date"].append(dict(calendar_date=date, calendar_year=day.year, month_start=month(date),
            is_weekend=day.weekday() >= 5, holiday_name=holidays.get(date, {}).get("holiday_name"),
            is_bank_holiday=holidays.get(date, {}).get("is_bank_holiday", False)))
        day += dt.timedelta(days=1)
    models["audit_unresolved_campaign_ids"] = [dict(model_table="fact_vendor_delivery", mapping_source_system=key[0],
        campaign_match_token=key[1], campaign_resolution_status=key[2], affected_rows=len(rows))
        for key, rows in group(vendor, ["mapping_source_system", "campaign_match_token", "campaign_resolution_status"]).items()]
    assert len(models) == 78
    return models


def build_marts(models, gold):
    marts = {}
    vendor = models["fact_vendor_delivery"]
    vendor_keys = "source_table platform report_date report_end_date source_campaign_id resolved_campaign_key campaign_resolution_status currency click_event conversion_event conversion_value_event".split()
    daily = roll(vendor, vendor_keys, ["reported_impressions", "reported_clicks", "spend_amount", "reported_conversions", "reported_conversion_value"], {"source_row_count": lambda row: True})
    for row in daily:
        row["reported_click_rate"] = ratio(row["reported_clicks"], row["reported_impressions"])
        row["cost_per_reported_click"] = ratio(row["spend_amount"], row["reported_clicks"])
        row["cost_per_thousand_impressions"] = ratio(1000 * row["spend_amount"], row["reported_impressions"])
        row["source_campaign_name"] = row["source_campaign_id"]
    marts["mart_vendor_media_daily"] = daily
    marts["mart_platform_conversion_efficiency"] = [{**row,
        "platform_conversion_rate": ratio(row["reported_conversions"], row["reported_clicks"]),
        "platform_reported_cpa": ratio(row["spend_amount"], row["reported_conversions"]),
        "platform_reported_value_to_spend": ratio(row["reported_conversion_value"], row["spend_amount"])} for row in daily]
    coverage = [{**row, "report_month": month(row["report_date"])} for row in daily]
    marts["mart_campaign_attribution_coverage"] = roll(coverage,
        ["report_month", "platform", "currency", "campaign_resolution_status"], ["spend_amount", "source_row_count"])
    delivery = models["fact_paid_ad_delivery_daily"]
    marts["mart_demo_paid_media_daily"] = roll(delivery,
        "report_date campaign_key source_campaign_id platform format currency pack_version".split(),
        ["impressions", "link_clicks", "response_starts", "response_submissions", "spend_usd"])
    marts["mart_demo_paid_reach_window"] = models["fact_paid_reach_window"]
    apps = {row["application_id"]: row for row in models["fact_demo_application"]}
    leads = {row["lead_id"]: row for row in models["fact_demo_lead"]}
    account_app = group(models["fact_demo_account"], ["application_id"])
    apps_lead = group(models["fact_demo_application"], ["lead_id"])
    lead_sub = group(models["fact_demo_lead"], ["submission_id"])
    cohorts = []
    for submission in models["fact_paid_submission"]:
        linked_leads = lead_sub[(submission["submission_id"],)]
        linked_apps = [app for lead in linked_leads for app in apps_lead[(lead["lead_id"],)]]
        linked_accounts = [account for app in linked_apps for account in account_app[(app["application_id"],)]]
        eligible = submission["link_status"].lower() != "duplicate_response"
        row = {**submission, "submission_month": month(submission["submitted_at"]), "submissions": 1,
               "eligible_submissions": int(eligible), "duplicate_submissions": int(not eligible)}
        stage_values = {"leads": bool(linked_leads), "qualified_leads": any(lead["qualified_at"] for lead in linked_leads),
            "applications": bool(linked_apps), "approved_applications": any(app["application_status"] == "APPROVED" for app in linked_apps),
            "opened_accounts": bool(linked_accounts), "funded_accounts": any(a["funding_status"] == "funded" for a in linked_accounts)}
        row.update({"submissions_with_" + key: int(eligible and value) for key, value in stage_values.items()})
        cohorts.append(row)
    marts["mart_demo_submission_funnel"] = roll(cohorts,
        "submission_month campaign_key source_campaign_id platform format pack_version".split(),
        ["submissions", "eligible_submissions", "duplicate_submissions"] + ["submissions_with_" + key for key in stage_values])

    branch_market = {row["branch_code"]: row["market_code"] for row in models["dim_branch"]}
    banking = [{**row, "opening_month": month(row["opened_date"]), "market_id": branch_market.get(row["booking_branch_code"])}
               for row in models["fact_banking_account"]]
    funding = roll(banking, ["opening_month", "product_id", "market_id"],
                   counts={"opened_accounts": lambda row: True, "funded_accounts": lambda row: row["funded_flag"] is True})
    marts["mart_banking_funded_accounts_monthly"] = funding
    funding_lookup = {(row["opening_month"], row["product_id"], row["market_id"]): row for row in funding}
    targets = []
    for row in models["fact_sales_target_monthly"]:
        actual = funding_lookup.get((row["target_month"], row["product_id"], row["market_id"]), {})
        targets.append({**row, "opened_accounts": actual.get("opened_accounts", 0), "funded_accounts": actual.get("funded_accounts", 0),
            "funded_account_attainment": ratio(actual.get("funded_accounts", 0), row["target_funded_accounts"])})
    marts["mart_sales_target_attainment_monthly"] = targets
    profiles = {row["customer_id"]: row for row in models["dim_customer"]}
    first = {}
    for row in sorted(banking, key=lambda row: (row["opened_date"], row["relationship_account_ref"])):
        if row["funded_flag"] and row["new_to_bank_flag"] and row["modeled_customer_id"]:
            first.setdefault(row["modeled_customer_id"], {**row, "acquisition_month": row["opening_month"],
                "segment_id": profiles.get(row["modeled_customer_id"], {}).get("segment_id")})
    acquisition = roll(first.values(), "acquisition_month product_id market_id segment_id resolved_campaign_key campaign_resolution_status".split(),
                       counts={"new_funded_customers": lambda row: True})
    marts["mart_new_funded_customers_monthly"] = acquisition
    monthly_total = Counter()
    for row in acquisition:
        monthly_total[row["acquisition_month"]] += row["new_funded_customers"]
    marts["mart_customer_acquisition_share"] = [{**row, "acquisition_share": ratio(row["new_funded_customers"], monthly_total[row["acquisition_month"]])} for row in acquisition]
    quality_rows = [{**row, "application_month": month(row["app_received_ts"]),
        "segment_id": profiles.get(row["modeled_customer_id"], {}).get("segment_id")} for row in models["fact_banking_application"] if row["test_record_flag"] is False]
    quality = roll(quality_rows, "application_month product_id market_cd segment_id mapping_source_campaign_id resolved_campaign_key campaign_resolution_status".split(),
        counts={"applications": lambda row: True, "approved_applications": lambda row: row["application_status"] == "APPROVED",
                "declined_applications": lambda row: row["application_status"] == "DECLINED"})
    for row in quality:
        row["approval_rate"] = ratio(row["approved_applications"], row["applications"])
        row["rejection_rate"] = ratio(row["declined_applications"], row["applications"])
    marts["mart_application_quality_monthly"] = quality

    web_submits = defaultdict(list)
    for event in models["fact_web_event"]:
        if event["event_name"].lower() == "application_submit":
            web_submits[event["ga_session_id"]].append(event["event_timestamp"])
    sessions = [{**row, "session_date": row["session_start_time"], "sessions": 1,
        "sessions_with_engagement_flag": int(row["session_engaged"] is not None), "engaged_sessions": int(row["session_engaged"] is True),
        "sessions_with_application_submit": int(any(date >= row["session_start_time"] for date in web_submits[row["ga_session_id"]]))}
        for row in models["fact_web_session"]]
    marts["mart_website_engagement_daily"] = roll(sessions,
        "session_date landing_page_path device_category mapping_source_campaign_id resolved_campaign_key campaign_resolution_status".split(),
        ["sessions", "sessions_with_engagement_flag", "engaged_sessions", "sessions_with_application_submit"])
    marts["mart_email_engagement_daily"] = [{**row, "delivery_rate": ratio(row["delivered"], row["sent"]),
        "bounce_rate": ratio(row["hard_soft_bounces"], row["sent"]), "email_click_rate": ratio(row["unique_clicks"], row["delivered"]),
        "opt_out_rate": ratio(row["opt_outs"], row["delivered"])} for row in models["fact_email_daily"]]
    response_jobs = group(models["fact_direct_mail_response"], ["recipient_job_id"])
    job_rows = []
    for job in models["fact_direct_mail_fulfillment"]:
        responses = [row for row in response_jobs[(job["recipient_job_id"],)] if row["response_ts"] >= job["mail_date"]]
        delivered = job["mail_status"].upper() == "DELIVERED"
        job_rows.append({**job, "mail_month": month(job["mail_date"]), "mail_jobs": 1, "delivered_jobs": int(delivered),
            "delivered_jobs_with_response": int(delivered and bool(responses)),
            "delivered_jobs_with_qr_scan": int(delivered and any(row["response_method"].upper() == "QR_SCAN" for row in responses)),
            "linked_response_events": len(responses)})
    mail = roll(job_rows, "mail_month mapping_source_campaign_id resolved_campaign_key campaign_resolution_status addr_market".split(),
                 ["mail_jobs", "delivered_jobs", "delivered_jobs_with_response", "delivered_jobs_with_qr_scan", "linked_response_events", "postage_usd"])
    for row in mail:
        row["delivered_job_response_rate"] = ratio(row["delivered_jobs_with_response"], row["delivered_jobs"])
    marts["mart_direct_mail_performance_monthly"] = mail
    order_totals = {row["order_no"]: row for row in roll(job_rows, ["order_no"], ["mail_jobs", "delivered_jobs", "delivered_jobs_with_response"])}
    marts["mart_direct_mail_order_economics"] = [{**row, **order_totals.get(row["order_no"], {}), "cost_currency": "UNSPECIFIED",
        "estimated_cost_per_responding_job": ratio(number(row["estimated_cost_new"]), order_totals.get(row["order_no"], {}).get("delivered_jobs_with_response", 0))}
        for row in models["fact_direct_mail_order"]]
    offline = []
    for table, date, geo, channel, metric, value in [
        ("fact_offline_interaction", "interaction_time", "market_ref", None, "offline_interactions", None),
        ("fact_broadcast_as_run", "actual_time", "market_code", "broadcast_tv", "aired_spots", None),
        ("fact_billboard_delivery", "week_start", "market_code", "billboard", "reported_billboard_impressions", "reported_impressions"),
        ("fact_dooh_play", "play_timestamp", None, "dooh", "plays", "play_count")]:
        for row in models[table]:
            if table == "fact_broadcast_as_run" and row["air_status"].upper() != "AIRED":
                continue
            offline.append(dict(observation_month=month(row[date]), source_channel=channel or row["channel_system"], metric=metric,
                geography_source_value=row[geo] if geo else None, metric_value=row[value] if value else 1,
                **{key: row[key] for key in ("mapping_source_campaign_id", "resolved_campaign_key", "campaign_resolution_status")}))
    marts["mart_offline_activity_monthly"] = roll(offline,
        "observation_month source_channel mapping_source_campaign_id resolved_campaign_key campaign_resolution_status geography_source_value metric".split(), ["metric_value"])

    events = group(models["fact_demo_experiment_event"], ["assignment_id"])
    experiment_rows = []
    for config in models["dim_demo_experiment_variant"]:
        members = [row for row in models["fact_demo_experiment_assignment"] if row["experiment_id"] == config["experiment_id"] and
            row["variant_id"] == config["variant_id"] and row["consent_state"] == "analytics_consent" and config["window_start"] <= row["assigned_at"] <= config["window_end"]]
        eligible = {row["unit_id"] for row in members}
        converted = {row["unit_id"] for row in members if any(event["event_type"] == config["primary_event"] and
            row["assigned_at"] <= event["event_at"] <= config["window_end"] for event in events[(row["assignment_id"],)])}
        experiment_rows.append({**config, "eligible_units": len(eligible), "converted_units": len(converted), "primary_event_rate": ratio(len(converted), len(eligible))})
    marts["mart_demo_experiment_variant"] = experiment_rows
    statistical_functions = [node for node in ast.parse(gold["experiment-comparison"]).body if isinstance(node, ast.FunctionDef)]
    math_scope = {"math": math, "NormalDist": NormalDist}
    exec(compile(ast.Module(body=statistical_functions, type_ignores=[]), "statistics", "exec"), math_scope)
    comparisons = []
    for row in experiment_rows:
        if row["variant_id"] == "A":
            continue
        control = next(control for control in experiment_rows if control["experiment_id"] == row["experiment_id"] and control["variant_id"] == "A")
        effect, relative, low, high, p = math_scope["compare_proportions"](control["converted_units"], control["eligible_units"], row["converted_units"], row["eligible_units"], .95)
        comparisons.append(dict(experiment_id=row["experiment_id"], variant_id=row["variant_id"], control_variant="A", absolute_lift=effect,
            relative_lift=relative, difference_ci_lower=low, difference_ci_upper=high, nominal_two_sided_p_value=p,
            confidence_level=.95, nominal_significant=p < .05, comparison_status="nominal_comparison_available"))
    marts["mart_demo_experiment_comparison"] = comparisons

    bank_lookup = {row["relationship_account_ref"]: row for row in banking}
    value_rows = []
    for row in models["fact_banking_relationship_monthly"]:
        account = bank_lookup[row["relationship_account_ref"]]
        value_rows.append({**row, "booking_market_id": account["market_id"], **{k: account[k] for k in
            ("mapping_source_campaign_id", "resolved_campaign_key", "campaign_resolution_status")},
            "interest_income_proxy_usd": row["interest_income_usd"], "fee_income_proxy_usd": row["fee_income_usd"],
            "funding_cost_proxy_usd": row["funding_cost_usd"], "servicing_cost_proxy_usd": row["servicing_cost_usd"],
            "reported_net_contribution_usd": row["net_relationship_contribution_usd"]})
    marts["mart_banking_relationship_contribution_monthly"] = roll(value_rows,
        "value_snapshot_month product_id booking_market_id mapping_source_campaign_id resolved_campaign_key campaign_resolution_status data_status".split(),
        ["interest_income_proxy_usd", "fee_income_proxy_usd", "funding_cost_proxy_usd", "servicing_cost_proxy_usd", "reported_net_contribution_usd"],
        {"observed_accounts": lambda row: True})
    demo_accounts = {row["account_id"]: row for row in models["fact_demo_account"]}
    demo_value = [{**row, **{k: demo_accounts[row["account_id"]][k] for k in ("campaign_key", "source_campaign_id", "product_id", "market_id")}}
                  for row in models["fact_demo_relationship_monthly"]]
    marts["mart_demo_relationship_value_monthly"] = roll(demo_value,
        "value_month campaign_key product_id market_id value_status pack_version".split(), ["net_interest_income_usd", "net_relationship_contribution_usd"], {"observed_accounts": lambda row: True})
    economy = []
    for setup in models["dim_paid_source_campaign"]:
        native = setup["source_campaign_id"]
        campaign_leads = [row for row in leads.values() if row["source_campaign_id"] == native]
        campaign_apps = [row for row in apps.values() if row["source_campaign_id"] == native]
        campaign_accounts = [row for row in demo_accounts.values() if row["source_campaign_id"] == native and row["funding_status"] == "funded"]
        account_ids = {row["account_id"] for row in campaign_accounts}
        cost = round(sum(number(row["spend_usd"]) for row in delivery if row["source_campaign_id"] == native), 2)
        contribution = round(sum(number(row["net_relationship_contribution_usd"]) for row in demo_value if row["account_id"] in account_ids), 2)
        economy.append({**setup, "platform_spend_usd": cost, "crm_leads": len(campaign_leads),
            "qualified_leads": sum(bool(row["qualified_at"]) for row in campaign_leads), "applications": len(campaign_apps),
            "approved_applications": sum(row["application_status"] == "APPROVED" for row in campaign_apps),
            "funded_accounts": len(account_ids), "funded_customers": len({row["customer_id"] for row in campaign_accounts}),
            "observed_contribution_usd": contribution if account_ids else None, "contribution_months": 3,
            "cost_per_lead_usd": ratio(cost, len(campaign_leads)), "cost_per_funded_account_usd": ratio(cost, len(account_ids)),
            "attributed_observed_return": ratio(contribution - cost, cost) if account_ids else None,
            "return_status": "observed_return_available" if account_ids else "no_funded_accounts"})
    marts["mart_demo_campaign_economics"] = economy
    marts["mart_demo_campaign_budget_utilization"] = [{**row, "budget_utilization": ratio(row["platform_spend_usd"], row["planned_budget_usd"])} for row in economy]
    recon = models["fact_demo_finance_reconciliation"]
    marts["mart_demo_finance_reconciliation_monthly"] = roll(recon, ["spend_month", "currency", "reconciliation_status"],
        ["invoice_net_usd", "gl_net_usd", "invoice_minus_gl_usd"], {"finance_links": lambda row: True})
    posted = group(models["fact_demo_gl_posting"], ["source_campaign_id", "accounting_month", "currency", "pack_version"])
    three_source = []
    for invoice in models["fact_demo_invoice"]:
        key = invoice["source_campaign_id"], invoice["spend_month"], invoice["currency"], invoice["pack_version"]
        spend = round(sum(number(row["spend_usd"]) for row in delivery if row["source_campaign_id"] == key[0] and month(row["report_date"]) == key[1]), 2)
        gl = sum(number(row["debit_usd"]) - number(row["credit_usd"]) for row in posted[key])
        three_source.append({**invoice, "platform_spend_usd": spend, "invoice_net_usd": invoice["net_invoice_usd"], "posted_gl_net_usd": gl,
            "invoice_media_minus_platform_usd": round(number(invoice["media_usd"]) - spend, 2),
            "posted_minus_invoice_usd": round(gl - number(invoice["net_invoice_usd"]), 2), "comparison_status": "matched"})
    marts["mart_demo_three_source_cost_reconciliation"] = three_source
    invoice_rows = []
    invoice_keys = "mapping_source_system campaign_match_token invoice_period_start invoice_period_end currency_code".split()
    for values, records in group(models["fact_vendor_invoice_line"], invoice_keys).items():
        row = dict(zip(invoice_keys, values))
        match = [d for d in vendor if d["mapping_source_system"] == row["mapping_source_system"] and d["campaign_match_token"] == row["campaign_match_token"]
                 and d["currency"].upper() == row["currency_code"].upper() and d["report_date"] >= row["invoice_period_start"] and d["report_end_date"] <= row["invoice_period_end"]]
        row.update(currency=row["currency_code"].upper(), invoice_lines=len(records), credit_lines=sum("CREDIT" in r["invoice_line_type"].upper() for r in records),
            reported_invoice_amount=sum(number(r["invoice_amount_new"]) for r in records),
            reported_tax_amount=sum(number(r["tax_amount_new"]) for r in records), platform_delivery_rows=len(match),
            platform_spend_amount=round(sum(number(d["spend_amount"]) for d in match), 2) if match else None,
            comparison_status="reported_amount_cost_scope_review" if match else "no_comparable_delivery")
        row["reported_invoice_minus_platform"] = row["reported_invoice_amount"] - row["platform_spend_amount"] if match else None
        invoice_rows.append(row)
    marts["mart_vendor_invoice_platform_comparison"] = invoice_rows
    budgets = []
    for setup in models["dim_vendor_campaign"]:
        matches = [row for row in vendor if row["mapping_source_system"] == setup["mapping_source_system"] and row["campaign_match_token"] == setup["campaign_match_token"]
                   and row["currency"] == setup["currency"] and row["report_date"] >= setup["flight_start"] and row["report_end_date"] <= setup["flight_end"]]
        days = (dt.date.fromisoformat(setup["flight_end"]) - dt.date.fromisoformat(setup["flight_start"])).days + 1
        budget = setup["budget_amount"] * days if setup["budget_period"] == "daily" else setup["budget_amount"] if setup["budget_period"] in {"total", "lifetime"} else None
        spend = sum(row["spend_amount"] for row in matches) if matches else None
        budgets.append({**setup, "flight_budget_amount": budget, "eligible_spend_amount": spend,
            "budget_utilization": ratio(spend, budget) if spend is not None and setup["currency"] else None,
            "budget_comparison_status": "currency_unavailable" if not setup["currency"] else "budget_period_unavailable" if budget is None else "full_flight_budget_available_delivery"})
    marts["mart_vendor_campaign_budget_utilization"] = budgets
    marts["mart_brand_survey_wave"] = [{**row, "measurement_wave": row["measurement_wave"].upper()} for row in models["fact_brand_lift_survey"]]
    marts["mart_brand_comparison_eligibility"] = [{"campaign_ref": row["campaign_ref"], "market_code": row["market_code"],
        "pre_post_pair_available": False, "exposed_control_pair_available": False, "brand_awareness_pct_post_minus_pre_pp": None}
        for row in models["fact_brand_lift_survey"]]
    marts["mart_ecom_orders_monthly"] = roll([{**row, "order_month": month(row["order_ts"]), "order_status": row["order_status"].upper()}
        for row in models["fact_ecom_order"]], ["order_month", "currency", "order_status"],
        ["order_total_new", "tax_amount_new", "shipping_amount_new"], {"orders": lambda row: True})
    assert len(marts) == 29, set(marts)
    return marts


def write_table(connection, name, records, empty_columns=()):
    columns = list(dict.fromkeys([key for row in records for key in row] or empty_columns))
    assert columns, name
    declarations = []
    for column in columns:
        values = [row[column] for row in records if row.get(column) is not None]
        kind = "REAL" if values and isinstance(values[0], (int, float, Decimal)) else "TEXT"
        declarations.append('"' + column + '" ' + kind)
    connection.execute('CREATE TABLE "' + name + '" (' + ', '.join(declarations) + ')')
    placeholders = ', '.join('?' for _ in columns)
    def value(v):
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, (dict, list, tuple)):
            return json.dumps(v, default=json_default)
        return v
    connection.executemany('INSERT INTO "' + name + '" VALUES (' + placeholders + ')',
        [tuple(value(row.get(column)) for column in columns) for row in records])


def main():
    dqx, model_code, gold = [code(name) for name in ("03_silver_to_dq_dqx.ipynb", "04_dq_to_data_model.ipynb", "05_model_to_gold.ipynb")]
    scope, inputs = read_pass_records(dqx)
    spec = {}
    exec(model_code["model-specifications"], spec)
    exec(model_code["validate-publish"].split("coverage_rows = []")[0], spec)
    models = build_entities(spec, inputs)
    marts = build_marts(models, gold)
    case_models = literal(gold["conformed-gold-entities"], "CASE_MODELS")
    case_marts = literal(gold["conformed-gold-entities"], "CASE_MARTS")
    mart_catalog = []
    variables = {}
    for text in gold.values():
        for node in ast.parse(text).body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        variables[target.id] = node.value.value
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "add_mart":
                name, _, keys, lineage, note = node.value.args
                grain = keys.value if isinstance(keys, ast.Constant) else variables.get(keys.id, "Source reporting grain") if isinstance(keys, ast.Name) else "Source reporting grain"
                mart_catalog.append(dict(mart_table=name.value, grain_columns=grain, model_sources=lineage.value,
                                         row_count=len(marts[name.value]), metric_notes=note.value))
    entity_catalog = []
    for name, records in models.items():
        keys = spec["NATIVE"].get(name, (None, "Documented modeled key"))[1]
        entity_catalog.append(dict(gold_table=name, model_table=name, grain_columns=keys, row_count=len(records), note="Source-derived local POC preview"))
    coverage = []
    for table in inputs:
        targets = sorted(name for name, sources in spec["SOURCE_MODELS"].items() if table in sources)
        coverage.append(dict(dq_table=table, dq_rows=len(inputs[table]), selected_columns=list(scope["SILVER_SCHEMA"][table]),
            gold_tables=targets, use_cases=sorted(case for case, names in case_models.items() if set(targets) & set(names)),
            silver_contract_sha256=scope["SILVER_CONTRACT_SHA256"]))
    metric_defs = literal(gold["metric-policy"], "METRIC_DEFINITIONS")
    metric_names = ["metric_id", "business_definition", "formula", "time_basis", "currency_basis", "cost_basis"]
    metadata = {"gold_mart_catalog": mart_catalog, "gold_entity_catalog": entity_catalog, "gold_source_coverage": coverage,
        "gold_use_case_tables": [dict(use_case=case, gold_table=name, table_kind="entity") for case, names in case_models.items() for name in names]
            + [dict(use_case=case, gold_table=name, table_kind="mart") for case, names in case_marts.items() for name in names],
        "gold_kpi_dictionary": [{**dict(zip(metric_names, row)), "policy_version": "poc_existing_data_v1", "contribution_months": 3,
                                 "control_variant": "A", "nominal_confidence_level": .95} for row in metric_defs],
        "gold_use_case_readiness": [dict(use_case=case, reporting_marts=case_marts[case], remaining_requirements=remaining,
                                        implementation_status="supported_poc_metrics") for case, remaining in literal(gold["metric-policy"], "REMAINING_REQUIREMENTS").items()]}
    output = APP / "data"
    output.mkdir(exist_ok=True)
    path = output / "preview.db"
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as connection:
        for name, rows in {**models, **marts, **metadata}.items():
            empty = ["source_system", "source_campaign_id", "mapping_source_system", "campaign_match_token", "campaign_key", "approval_origin"]
            write_table(connection, name, rows, empty)
        connection.commit()
        assert connection.execute('SELECT SUM(funded_accounts) FROM mart_banking_funded_accounts_monthly').fetchone()[0] == 282
        assert connection.execute('SELECT SUM(submissions) FROM mart_demo_submission_funnel').fetchone()[0] == 1262
        assert connection.execute('SELECT COUNT(*) FROM gold_source_coverage').fetchone()[0] == 91
    connection.close()
    archive = output / "preview.db.gz"
    with path.open("rb") as source, gzip.open(archive, "wb") as target:
        target.write(source.read())
    path.unlink()
    print(f"Built {len(models)} entity tables, {len(marts)} marts and six metadata tables from 68,372 passing source rows.")
    print(f"Preview archive: {archive.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
