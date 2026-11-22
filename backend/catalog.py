"""The public reporting contract. Expressions and identifiers are server controlled."""

from dataclasses import dataclass


def total(field):
    return f"SUM(`{field}`)"


def rate(numerator, denominator, multiplier=1):
    return f"{multiplier}.0 * SUM(`{numerator}`) / NULLIF(SUM(`{denominator}`), 0)"


@dataclass(frozen=True)
class Metric:
    label: str
    table: str
    expression: str
    format: str
    description: str
    direction: str = "neutral"


@dataclass(frozen=True)
class Chart:
    title: str
    table: str
    kind: str
    dimensions: tuple
    measures: tuple
    note: str
    order: str = "label ASC"
    limit: int = 18
    raw: bool = False


def measure(name, expression, label, format="number"):
    return {"name": name, "expression": expression, "label": label, "format": format}


VENDOR = "mart_vendor_media_daily"
ECONOMICS = "mart_demo_campaign_economics"
FUNDING = "mart_banking_funded_accounts_monthly"
VALUES = "mart_banking_relationship_contribution_monthly"
WEB = "mart_website_engagement_daily"
EMAIL = "mart_email_engagement_daily"
EXPERIMENT = "mart_demo_experiment_variant"
FINANCE = "mart_demo_three_source_cost_reconciliation"

PAGES = {
    "overview": {
        "title": "Executive overview", "subtitle": "The complete picture of marketing performance.",
        "eyebrow": "MARKETING INTELLIGENCE", "table": ECONOMICS,
        "metrics": [
            Metric("Media investment", VENDOR, total("spend_amount"), "currency", "Native vendor delivery cost in the selected currency."),
            Metric("CRM leads", ECONOMICS, total("crm_leads"), "number", "Synthetic explicit campaign cohorts; cohort period follows campaign flight start.", "up"),
            Metric("Funded accounts", FUNDING, total("funded_accounts"), "number", "Banking funded status grouped by opening month.", "up"),
            Metric("Observed contribution", VALUES, total("reported_net_contribution_usd"), "usd", "Signed synthetic banking income and cost proxies in the observation month.", "up"),
        ],
        "charts": [
            Chart("Media investment over time", VENDOR, "area", ("report_date",),
                  (measure("spend", total("spend_amount"), "Media spend", "currency"),),
                  "Vendor delivery · source reporting date · selected currency", limit=180),
            Chart("Investment by platform", VENDOR, "horizontal", ("platform",),
                  (measure("spend", total("spend_amount"), "Media spend", "currency"),),
                  "A consistent platform delivery cost basis", "spend DESC"),
            Chart("Funded accounts by month", FUNDING, "bar", ("opening_month",),
                  (measure("funded", total("funded_accounts"), "Funded accounts"),),
                  "Banking accounts · opening-month cohort"),
        ],
    },
    "campaigns": {
        "title": "Campaign & paid media", "subtitle": "Follow investment from platform activity to measurable outcomes.",
        "eyebrow": "CAMPAIGN PERFORMANCE", "table": "mart_platform_conversion_efficiency",
        "metrics": [
            Metric("Media investment", VENDOR, total("spend_amount"), "currency", "Sum of platform-reported delivery cost."),
            Metric("Reported impressions", VENDOR, total("reported_impressions"), "compact", "Additive platform-reported impressions."),
            Metric("Reported click rate", VENDOR, rate("reported_clicks", "reported_impressions"), "percent", "Ratio of total labeled native clicks to total impressions. Native click definitions vary by platform.", "up"),
            Metric("Cost per reported click", VENDOR, rate("spend_amount", "reported_clicks"), "currency", "Selected-currency delivery cost divided by reported clicks.", "down"),
        ],
        "charts": [
            Chart("Platform investment", VENDOR, "horizontal", ("platform",),
                  (measure("spend", total("spend_amount"), "Spend", "currency"),), "Click a platform to filter this workspace.", "spend DESC"),
            Chart("Campaign efficiency", ECONOMICS, "scatter", ("source_campaign_id",),
                  (measure("cost", total("platform_spend_usd"), "Demo spend", "usd"),
                   measure("funded", total("funded_accounts"), "Funded accounts")),
                  "Synthetic source campaigns · explicit funded-account outcomes", "cost DESC"),
            Chart("Investment trend", VENDOR, "area", ("report_date",),
                  (measure("spend", total("spend_amount"), "Spend", "currency"),), "Vendor source reporting dates", limit=180),
        ],
    },
    "acquisition": {
        "title": "Customer acquisition", "subtitle": "Understand the customers and products behind acquisition growth.",
        "eyebrow": "CUSTOMER INTELLIGENCE", "table": "mart_application_quality_monthly",
        "metrics": [
            Metric("New funded customers", "mart_new_funded_customers_monthly", total("new_funded_customers"), "number", "Distinct resolved new-to-bank customers; first qualifying funded account in the snapshot.", "up"),
            Metric("Applications", "mart_application_quality_monthly", total("applications"), "number", "Explicitly non-test banking applications, grouped by received month."),
            Metric("Approval rate", "mart_application_quality_monthly", rate("approved_applications", "applications"), "percent", "Current approved applications divided by eligible applications.", "up"),
            Metric("Decline rate", "mart_application_quality_monthly", rate("declined_applications", "applications"), "percent", "Current declined applications divided by eligible applications.", "down"),
        ],
        "charts": [
            Chart("From lead to funded account", ECONOMICS, "funnel", (),
                  tuple(measure(field, total(field), label) for field, label in [
                      ("crm_leads", "CRM leads"), ("qualified_leads", "Qualified leads"),
                      ("applications", "Applications"), ("approved_applications", "Approved"), ("funded_accounts", "Funded accounts")]),
                  "Synthetic campaign cohorts · child stages aggregated before joining"),
            Chart("Acquisition by customer segment", "mart_new_funded_customers_monthly", "horizontal", ("segment_id",),
                  (measure("customers", total("new_funded_customers"), "New funded customers"),),
                  "Current customer reference segment · first qualifying account", "customers DESC"),
            Chart("Submission cohort conversion", "mart_demo_submission_funnel", "heatmap", ("submission_month", "platform"),
                  (measure("rate", rate("submissions_with_funded_accounts", "eligible_submissions"), "Funded-account submission rate", "percent"),),
                  "Synthetic submission month · eligible submissions are the denominator", limit=100),
        ],
    },
    "digital": {
        "title": "Digital & offline", "subtitle": "Explore engagement across the channels that connect with your audience.",
        "eyebrow": "CHANNEL ENGAGEMENT", "table": WEB,
        "metrics": [
            Metric("Website sessions", WEB, total("sessions"), "compact", "Source session IDs; events are aggregated before joining."),
            Metric("Web application rate", WEB, rate("sessions_with_application_submit", "sessions"), "percent", "Sessions with a dated application-submit event divided by sessions.", "up"),
            Metric("Email deliveries", EMAIL, total("delivered"), "compact", "Reported deliveries from campaign/send rollups."),
            Metric("Email click rate", EMAIL, rate("unique_clicks", "delivered"), "percent", "Reported unique clicks divided by delivered messages; uniqueness is scoped to each send.", "up"),
        ],
        "charts": [
            Chart("Website engagement", WEB, "line", ("session_date",),
                  (measure("sessions", total("sessions"), "Sessions"), measure("engaged", total("engaged_sessions"), "Engaged sessions")),
                  "Source session date · known engagement flags", limit=180),
            Chart("Email delivery & engagement", EMAIL, "horizontal", ("cmpgn_id",),
                  (measure("delivered", total("delivered"), "Delivered"), measure("clicked", total("unique_clicks"), "Unique clicks")),
                  "Source campaign/send rollups", "delivered DESC", 10),
            Chart("Direct-mail response", "mart_direct_mail_performance_monthly", "bar", ("mail_month",),
                  (measure("delivered", total("delivered_jobs"), "Delivered jobs"),
                   measure("responded", total("delivered_jobs_with_response"), "Jobs with response")),
                  "Delivered-job grain · responses dated on or after mailing"),
        ],
    },
    "finance": {
        "title": "Financial performance", "subtitle": "Connect investment, observed contribution and financial controls.",
        "eyebrow": "FINANCE & BUSINESS VALUE", "table": "mart_vendor_invoice_platform_comparison",
        "metrics": [
            Metric("Observed contribution", VALUES, total("reported_net_contribution_usd"), "usd", "Observed banking relationship proxies, retaining their source signs.", "up"),
            Metric("Demo invoice cost", FINANCE, total("invoice_net_usd"), "usd", "Synthetic net invoice amount including its reported service fee."),
            Metric("Demo posted GL", FINANCE, total("posted_gl_net_usd"), "usd", "Synthetic ledger debit less credit."),
            Metric("Funded target attainment", "mart_sales_target_attainment_monthly", rate("funded_accounts", "target_funded_accounts"), "percent", "Actual funded status by opening month and booking market, within one selected plan version.", "up"),
        ],
        "charts": [
            Chart("Observed contribution bridge", VALUES, "waterfall", (),
                  (measure("interest", total("interest_income_proxy_usd"), "Interest", "usd"),
                   measure("fees", total("fee_income_proxy_usd"), "Fees", "usd"),
                   measure("funding", "-SUM(`funding_cost_proxy_usd`)", "Funding cost", "usd"),
                   measure("servicing", "-SUM(`servicing_cost_proxy_usd`)", "Servicing cost", "usd")),
                  "Source income proxies and applicable costs · signed USD values"),
            Chart("Three views of demo cost", FINANCE, "bar", ("spend_month",),
                  (measure("platform", total("platform_spend_usd"), "Platform media", "usd"),
                   measure("invoice", total("invoice_net_usd"), "Invoice with fee", "usd"),
                   measure("ledger", total("posted_gl_net_usd"), "Posted GL", "usd")),
                  "Synthetic campaign/month comparison · cost representations remain distinct"),
            Chart("Sales plan versus actual", "mart_sales_target_attainment_monthly", "bar", ("target_month",),
                  (measure("target", total("target_funded_accounts"), "Target"), measure("actual", total("funded_accounts"), "Funded actual")),
                  "One plan version · product and booking-market grain"),
        ],
    },
    "experiments": {
        "title": "Experiments & brand", "subtitle": "Evaluate measured outcomes with their observation windows and uncertainty.",
        "eyebrow": "MEASUREMENT & LEARNING", "table": "mart_demo_experiment_comparison",
        "metrics": [
            Metric("Eligible experiment units", EXPERIMENT, total("eligible_units"), "number", "Distinct consented units inside their configured assignment windows."),
            Metric("Converted units", EXPERIMENT, total("converted_units"), "number", "Distinct eligible units with the configured primary event after assignment."),
            Metric("Primary-event rate", EXPERIMENT, rate("converted_units", "eligible_units"), "percent", "Combined descriptive event rate; compare variants in the chart below."),
            Metric("Survey cells", "mart_brand_survey_wave", "COUNT(*)", "number", "Supplied aggregate survey wave rows; these are not unique respondent counts."),
        ],
        "charts": [
            Chart("Experiment variant conversion", EXPERIMENT, "bar", ("variant_id",),
                  (measure("rate", rate("converted_units", "eligible_units"), "Primary-event rate", "percent"),),
                  "Synthetic assigned units · configured primary outcome"),
            Chart("Uplift and uncertainty", "mart_demo_experiment_comparison", "interval", ("variant_id",),
                  (measure("effect", "absolute_lift", "Absolute lift", "percent"),
                   measure("lower", "difference_ci_lower", "Interval lower", "percent"),
                   measure("upper", "difference_ci_upper", "Interval upper", "percent")),
                  "Nominal interval versus control · an interval crossing zero does not establish a difference", raw=True),
            Chart("Reported brand awareness", "mart_brand_survey_wave", "bar", ("survey_wave_id",),
                  (measure("awareness", "brand_awareness_pct", "Reported awareness", "percentage_points"),),
                  "Individual aggregate survey cells · campaign and market scopes remain distinct", limit=10, raw=True),
        ],
    },
}

# The date and campaign roles are explicit to avoid interpreting vendor IDs as enterprise keys.
DATE_FIELDS = {
    "mart_vendor_media_daily": "report_date", "mart_platform_conversion_efficiency": "report_date",
    "mart_campaign_attribution_coverage": "report_month", "mart_demo_campaign_economics": "flight_start",
    "mart_demo_paid_media_daily": "report_date", "mart_demo_submission_funnel": "submission_month",
    "mart_banking_funded_accounts_monthly": "opening_month", "mart_new_funded_customers_monthly": "acquisition_month",
    "mart_customer_acquisition_share": "acquisition_month", "mart_application_quality_monthly": "application_month",
    "mart_banking_relationship_contribution_monthly": "value_snapshot_month",
    "mart_demo_relationship_value_monthly": "value_month", "mart_website_engagement_daily": "session_date",
    "mart_email_engagement_daily": "send_dt", "mart_direct_mail_performance_monthly": "mail_month",
    "mart_offline_activity_monthly": "observation_month", "mart_demo_three_source_cost_reconciliation": "spend_month",
    "mart_demo_finance_reconciliation_monthly": "spend_month", "mart_sales_target_attainment_monthly": "target_month",
    "mart_vendor_invoice_platform_comparison": "invoice_period_start", "mart_brand_survey_wave": "survey_date",
    "mart_demo_experiment_variant": "window_start", "mart_ecom_orders_monthly": "order_month",
}
MONTHLY = {name for name, field in DATE_FIELDS.items() if "month" in field}
META_TABLES = {"gold_mart_catalog", "gold_entity_catalog", "gold_source_coverage", "gold_use_case_tables",
               "gold_kpi_dictionary", "gold_use_case_readiness"}
DEMO_CAMPAIGN_TABLES = {"mart_demo_campaign_economics", "mart_demo_paid_media_daily", "mart_demo_paid_reach_window",
                       "mart_demo_submission_funnel", "mart_demo_experiment_variant", "mart_demo_relationship_value_monthly",
                       "mart_demo_campaign_budget_utilization", "dim_campaign", "dim_paid_source_campaign"}
