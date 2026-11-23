# Use-case analytics on Gold

Business logic is defined in `backend/catalog.py`. Each metric/chart issues a read-only query against the selected Gold location; `dashboard-data-mapping.csv` lists all 42 dashboard elements and their columns. There is no physical Use Cases publication step and no new quota usage.

| Use case | App surface | Existing Gold foundation | Practical scope |
|---|---|---|---|
| UC01 Funnel and acquisition economics | Overview; Customer Acquisition | `mart_demo_campaign_economics`, `mart_demo_submission_funnel`, banking funding/application marts | Explicit synthetic campaign cohorts remain separate from operational banking totals; no inferred cross-domain attribution |
| UC02 Paid media | Campaign & Paid Media | `mart_vendor_media_daily`, `mart_platform_conversion_efficiency`, `mart_demo_campaign_economics` | Platform spend, clicks/impressions and campaign economics; native conversions keep their definitions |
| UC03 Website and email | Digital & Offline | `mart_website_engagement_daily`, `mart_email_engagement_daily` | Sessions/engagement, deliveries and unique clicks scoped to sends |
| UC04 Experiments | Experiments & Brand | `mart_demo_experiment_variant`, `mart_demo_experiment_comparison` | Configured primary event, variants and nominal intervals; no automatic significant-winner claim |
| UC05 Offline/omnichannel | Digital & Offline; Gold Explorer | `mart_direct_mail_performance_monthly`, `mart_direct_mail_order_economics`, `mart_offline_activity_monthly` | Mail response visual; other offline detail in explorer. A deterministic full customer journey is not established |
| UC06 Segmentation | Customer Acquisition | `mart_new_funded_customers_monthly`, `mart_customer_acquisition_share`, `mart_application_quality_monthly` | First funded customers, application quality and segment detail; not inferred customer identity |
| UC07 Contribution | Overview; Financial Performance | `mart_banking_relationship_contribution_monthly`, `mart_demo_relationship_value_monthly` | Observed signed income/cost proxies, separately scoped; not forecast LTV or accounting profit |
| UC08 Cost reconciliation | Financial Performance; Gold Explorer | `mart_demo_three_source_cost_reconciliation`, `mart_vendor_invoice_platform_comparison` | Three cost representations kept separate; timing, fees and currency need reconciliation |
| UC09 Targets/budgets | Financial Performance; Gold Explorer | `mart_sales_target_attainment_monthly`, `mart_vendor_campaign_budget_utilization`, `mart_demo_campaign_budget_utilization` | Compatible month/product/market targets with one plan version; campaign budgets available in explorer |
| UC10 Brand lift | Experiments & Brand; Gold Explorer | `mart_brand_survey_wave`, `mart_brand_comparison_eligibility` | Survey-cell observations and comparison eligibility; causal lift requires eligible treatment/control evidence |

Rows above identify Gold inputs, not a claim that every table has its own specialized chart. Shared `dim_campaign`, Gold policy metadata and source coverage provide naming and definitions. The optional e-commerce domain remains separate and can be inspected through its Gold entities/marts.

Campaign filters use enterprise campaign keys, and platform filters use the actual platform field. A Gold grain without the selected key produces an unavailable result, never an unchanged overall total. Existing mart measures are aggregated at their declared grain; the app does not flatten raw facts together or allocate spend/outcomes across campaigns arbitrarily.

The full uploaded Gold contract has 113 registered objects. A smaller publication supports only its available datasets. Missing columns, missing tables and denied permissions are reported per visual. No live failure substitutes preview values. Update the Gold pipeline first if additional business measures or attribution keys are required.
