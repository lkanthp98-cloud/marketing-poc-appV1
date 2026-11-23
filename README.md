# Marketing Intelligence - Gold-backed Databricks app

All business pages build use-case analytics on **Gold**. For the dedicated app boundary, run [08_publish_app_gold_subset.ipynb](notebooks/08_publish_app_gold_subset.ipynb) to publish **23 marts + dim_campaign + six metadata tables** from `media-poc.gold` into `source-data.app_gold`. Then connect the app to `source-data.app_gold`; deployment now defaults to that location. A separate Use Cases schema is not required.

The publisher creates **30 additional managed Delta tables** on the first run, so capacity must be available. It checks capacity, pins source versions, narrows metadata references and reconciles exact rows/types. It leaves source Gold unchanged and refreshes only its own destination tables. The app itself remains read-only. See [publication instructions and quota limitations](docs/APP_GOLD_SUBSET.md). This is not a confirmed fix for the separately reported telemetry error.

React and ECharts provide six business pages, a Gold Data Explorer and Ask Genie. Deployment explicitly uses **SQL_AUTH_MODE=app** and **GENIE_AUTH_MODE=app**: both authenticate as the Databricks-managed app service principal. The developer configures resource/data access once, then shares the app in Databricks UI with Can Use. Approved users open the app link after signing in, without individual warehouse/table/Genie grants. The 30-table SQL namespace is fixed server-side, and Genie conversations are isolated by signed browser/account sessions. Optional user modes preserve individual policies; identities never switch automatically after a failure. See [sharing and filter behavior](docs/SHARING_AND_FILTERS.md).

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

Follow [app identity setup](docs/APP_IDENTITY_SETUP.md) and [deployment](docs/DEPLOYMENT.md). Attach warehouse key `sql-warehouse` with Can use and Genie key `genie-space` with Can run. Grant the existing app principal USE CATALOG, USE SCHEMA and SELECT on `source-data.app_gold` using [the three setup statements](docs/grant_app_gold_read_access.sql). Databricks supplies OAuth credentials automatically; no personal token is required. Curate the Genie Agent on this dataset. The default bundle requests no delegated user data scopes; those are needed only for optional user modes. No tables are created by these grants.

`databricks.yml` and `deploy.ps1` attach existing resource IDs during bundle deployment. The script also runs the owner-authorized dataset grant helper before starting the app. In app SQL mode, Connection settings displays the deployment's fixed Gold location and explains shared access; old browser namespace preferences are ignored. User SQL mode retains per-browser locations and viewer permissions. [Genie setup](docs/GENIE_SETUP.md) describes its separate curation and attachment.

## Reporting integrity

Campaign names come from `dim_campaign`, with valid mart labels as a fallback. An ID fallback never overwrites a real name. Missing/conflicting labels produce explicit notices. Proposed campaign mappings are not approved by the app. Campaign and platform filters require compatible keys; for example, product/market/month funded-account totals have no campaign key and become unavailable under a campaign selection.

Platform and More filters now load actual choices with independent availability/error statuses. Refresh data reloads choices as well as reports; Currency/Plan cannot become unexplained blank selectors. Campaign, platform, product and market selections mark incompatible grains unavailable. [The supplied HTML reference](docs/LAYOUT_REFERENCE.md) informed business-first report tables, campaign-name labels and explicit grain/cost notes; its embedded preview numbers and GL accrual assumptions are not runtime data.

Vendor delivery, synthetic campaign cohorts and banking outcomes are distinct populations. Native currencies are never mixed. Platform cost, invoice cost and GL postings are compared separately, never added as independent expenses. Contribution proxies are not recognized revenue, causal ROI or forecast LTV. Rates use ratios of sums; absent denominators are unavailable. Monthly comparisons use complete, nonoverlapping calendar months. Fixed experiment windows retain their configured period; brand survey cells do not establish causal lift. Other unsupported filters are listed in metric details.

Queries bind filter values and restrict SQL identifiers/expressions to published contracts. Exports contain up to 10,000 filtered/searched rows and escape spreadsheet formula text. Viewer/namespace caches store column metadata for 60 seconds, never tokens or result rows. Connection cookies contain location preferences only and grant no permissions.

Run [the read-only Gold integrity audit](notebooks/07_gold_campaign_filter_integrity_audit.py) in Databricks to check actual campaign names, keys, mappings and grains. The app audit creates no tables. A screenshot or metadata export does not establish live data integrity.

## Validation

Run `python -m unittest discover -s backend/tests -q`, `npm.cmd run build`, then `npm.cmd run test:ui` with a local preview server running. Browser tests use PLAYWRIGHT_BASE_URL when specified. See [validation evidence](VALIDATION.md) for the current results and their scope.

No live Databricks execution or deployment was performed for this revision. Review warehouse authorization, Gold row-level reconciliation and Genie answers in your workspace before business acceptance.
