# Marketing Intelligence - Gold-backed Databricks app

All business pages build use-case analytics on **Gold**. For the dedicated app boundary, run [08_publish_app_gold_subset.ipynb](notebooks/08_publish_app_gold_subset.ipynb) to publish **23 marts + dim_campaign + six metadata tables** from `media-poc.gold` into `media-poc.app_gold`. Then connect the app to `media-poc.app_gold`; deployment now defaults to that location. A separate Use Cases schema is not required.

The publisher creates **30 additional managed Delta tables** on the first run, so capacity must be available. It checks capacity, pins source versions, narrows metadata references and reconciles exact rows/types. It leaves source Gold unchanged and refreshes only its own destination tables. The app itself remains read-only. See [publication instructions and quota limitations](docs/APP_GOLD_SUBSET.md). This is not a confirmed fix for the separately reported telemetry error.

React and ECharts provide six business pages, a Gold Data Explorer and Ask Genie. FastAPI queries Databricks SQL using the signed-in viewer's authorization. Campaign selectors show Gold master names while retaining campaign keys for filtering. Campaign/platform selections never silently return an unrelated overall total: unsupported Gold grains are explicitly unavailable.

| Page | Supported analysis |
|---|---|
| Executive Overview | Investment, campaign leads, banking funded accounts, observed contribution |
| Campaign & Paid Media | Delivery cost, native clicks/impressions, weighted efficiency, campaign economics |
| Customer Acquisition | Banking application quality, first funded customers, campaign submission cohorts and funnel |
| Digital & Offline | Website engagement, email deliveries/clicks and direct-mail response |
| Financial Performance | Relationship proxies, separate platform/invoice/GL cost representations, sales targets |
| Experiments & Brand | Configured experiment outcomes, nominal uncertainty and survey cells |
| Gold Data Explorer | Registered Gold marts/entities, schema, lineage, KPI dictionary and authorized schema metadata |
| Ask Genie | Text analytics through your independently curated Gold Genie space |

These are supported analyses for the ten requested use cases, not ten fully validated production applications. [Use-case mapping](docs/USE_CASES_ON_GOLD.md) documents coverage and limits. The 30-table app subset contains its documented source-to-mart lineage; it does not advertise all 113 source-Gold objects or claim all 91 feeds are needed by these reports. Broader TV/OOH, referral/call and e-commerce details remain in the original Gold schema.

## Local review

Use Python 3.11+ and Node 22.12+. Create a virtual environment, install `requirements-dev.txt`, run `npm.cmd ci` and `npm.cmd run build`, set DATA_MODE=preview, then run `python start.py`. Open http://localhost:8000. On Linux/macOS use npm and export DATA_MODE=preview.

The included read-only `data/preview.db.gz` is independently derived from synthetic source CSVs using Silver selection and DQ pass rules (68,372 accepted rows from 68,466 inputs). It is not a downloaded Databricks Gold snapshot. Its known unfiltered values include USD spend 790,179.109988, banking funded accounts 282, contribution proxy USD 105,265.94 and 480 experiment units with 81 conversions. These are local test baselines, not fixed expected live values.

## Deploy

Follow [deployment](docs/DEPLOYMENT.md). Attach warehouse key `sql-warehouse` and Genie key `genie-space`; enable `sql`/`genie` user authorization. `app.yaml` binds resource IDs through valueFrom and sets DATA_MODE=live. Databricks supplies the workspace host. Viewers need warehouse CAN USE plus the required Gold catalog/schema/table privileges. The app uses the forwarded viewer token and never silently falls back to the app service principal or sample data.

`databricks.yml` and `deploy.ps1` attach existing resource IDs during bundle deployment. [Genie setup](docs/GENIE_SETUP.md) describes curation and attachment. Connection settings now asks only for Gold catalog/schema. Old source profiles migrate to Gold; verify the selected location after upgrading. Genie space datasets remain separately managed and must also be curated on Gold.

## Reporting integrity

Campaign names come from `dim_campaign`, with valid mart labels as a fallback. An ID fallback never overwrites a real name. Missing/conflicting labels produce explicit notices. Proposed campaign mappings are not approved by the app. Campaign and platform filters require compatible keys; for example, product/market/month funded-account totals have no campaign key and become unavailable under a campaign selection.

Vendor delivery, synthetic campaign cohorts and banking outcomes are distinct populations. Native currencies are never mixed. Platform cost, invoice cost and GL postings are compared separately, never added as independent expenses. Contribution proxies are not recognized revenue, causal ROI or forecast LTV. Rates use ratios of sums; absent denominators are unavailable. Monthly comparisons use complete, nonoverlapping calendar months. Fixed experiment windows retain their configured period; brand survey cells do not establish causal lift. Other unsupported filters are listed in metric details.

Queries bind filter values and restrict SQL identifiers/expressions to published contracts. Exports contain up to 10,000 filtered/searched rows and escape spreadsheet formula text. Viewer/namespace caches store column metadata for 60 seconds, never tokens or result rows. Connection cookies contain location preferences only and grant no permissions.

Run [the read-only Gold integrity audit](notebooks/07_gold_campaign_filter_integrity_audit.py) in Databricks to check actual campaign names, keys, mappings and grains. The app audit creates no tables. A screenshot or metadata export does not establish live data integrity.

## Validation

Run `python -m unittest discover -s backend/tests -q`, `npm.cmd run build`, then `npm.cmd run test:ui` with a local preview server running. Browser tests use PLAYWRIGHT_BASE_URL when specified. See [validation evidence](VALIDATION.md) for the current results and their scope.

No live Databricks execution or deployment was performed for this revision. Review warehouse authorization, Gold row-level reconciliation and Genie answers in your workspace before business acceptance.
