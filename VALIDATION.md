# Gold-backed app validation - 23 November 2026

Validation uses the source-derived local sample and supplied explorer CSV contracts. No live Databricks query, deployment or financial acceptance was performed.

| Check | Result |
|---|---|
| Backend tests | 82 passed |
| TypeScript and production Vite build | Passed |
| Playwright browser scenarios | 14 passed |
| Dashboard columns and expressions | All 42 elements checked against Gold export fields |
| Business routing | All six report pages use Gold directly |
| Use Cases isolation | No Use Cases queries, schema reads or export reads; explicit disabled-layer requests rejected |
| Legacy profiles | Both/Use-Cases-only browser preferences migrate to Gold; old environment source modes cannot enable Use Cases |
| Campaign names | Master labels preserved over ID-only rows; deterministic missing/conflict labels; master disagreements disclosed |
| Campaign/platform/product/market filters | Exact source-key matching; incompatible grains marked unavailable; exports cannot return unfiltered totals |
| Baseline measures | Unfiltered local spend, impressions, funding, contribution and experiment results preserved |
| Gold reads | All 113 sample objects readable; 91 source coverage records |
| Schema reference | Four active foundation locations: 377 definitions, 4,817 columns; historical fifth export retained in contract only |
| Permissions/transport | Explicit app/user SQL modes, OAuth M2M header selection, no identity fallback, token redaction and viewer/auth/namespace cache isolation checked with mocks |
| Shared app boundary | Configured source-data.app_gold and 30-table allowlist enforced server-side; stale cookies ignored; cross-schema POST rejected |
| Owner grant helper | Existing principal discovery, exact 30-table verification and only three read grants checked with mocks |
| Genie | Lifecycle, conversation isolation, sample answers, SQL/results and browser tab checked; no live Genie calls |
| Audit notebook | Python syntax checked; Spark SQL audit execution pending in Databricks |
| App publisher | Exact 30-table contract, narrowed lineage/readiness, capacity and overwrite guards checked locally |
| Simulated source-data.app_gold namespace | All 24 KPI values and 18 chart results match the original fixture; no source-Gold data access |
| Live schema browser | Restricted to the selected app schema |
| Physical table changes | No live writes performed; publisher creates 30 app_gold tables on its first Databricks run |

Browser checks cover all six reports, Gold explorer, metric details, campaign names, campaign/platform scope, date filtering, saved/reset filters, unavailable results, schema, lineage, dictionary, table pagination/search/export, Gold-only connection settings, mobile navigation and Genie. Screenshots from the current tests are in artifacts, including gold-campaign-platform-filters.png. Older use-cases-explorer.png is historical evidence of the previous version and is not the current UI.

Known local test baselines: vendor USD delivery cost 790,179.109988; native impressions 56,797,673; native clicks 1,729,617; funded banking accounts 282; observed contribution proxy USD 105,265.94; experiment units 480 with 81 conversions. Fixture values are not fixed expected live outputs. Some ancillary sample fields are simplified.

The Vite build emits a bundle-size advisory (approximately 924 KB uncompressed / 306 KB gzipped). Build passes; initial-load and warehouse latency require workspace measurement. Local testing does not certify Spark execution, approved campaign crosswalks, actual Gold row integrity, Genie curation, quotas or business KPI approval. Run the read-only Gold audit and workspace acceptance checks after redeploying this version.

The publisher was checked with source-derived metadata and a simulated live SQLite namespace. Its generated IPYNB cells compile. Spark CTAS, Delta time travel, EXCEPT ALL, target grants and quota enforcement still require Databricks validation. The refresh is sequential; keep Gold writers and the app paused until the publisher reports success. Local preview still uses the original 113-table fixture; the separate app_gold integration test verifies only the 30 selected objects.

The default deployment now sets SQL_AUTH_MODE=app. Approved app users share the configured dataset; per-user policies require the optional user mode. App OAuth tests use the installed Databricks SDK with a mocked credential provider and HTTP transport, not a live token exchange. The browser shared-mode scenario uses mocked live connection metadata and checks the explicit access notice and read-only namespace fields. No live grants or deployment were executed.

Share-link update: Genie app OAuth, signed HttpOnly/Secure/SameSite browser sessions, browser/account/space/mode-bound conversation keys and cross-session follow-up/poll rejection are tested locally. The default bundle requests no delegated data scopes. Filter tests cover live choice fallbacks/status, product/market/plan reconciliation, refresh recovery, retained choices after metadata errors, and readable empty controls. Reference-inspired scorecards retain original Gold fields/values and full-column export; no new tables or metric formulas were added. The supplied HTML was inspected as a design reference and is not executed by the app.
