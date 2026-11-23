# Gold-backed app validation - 23 November 2026

Validation uses the source-derived local sample and supplied explorer CSV contracts. No live Databricks query, deployment or financial acceptance was performed.

| Check | Result |
|---|---|
| Backend tests | 52 passed |
| TypeScript and production Vite build | Passed |
| Playwright browser scenarios | 7 passed |
| Dashboard columns and expressions | All 42 elements checked against Gold export fields |
| Business routing | All six report pages use Gold directly |
| Use Cases isolation | No Use Cases queries, schema reads or export reads; explicit disabled-layer requests rejected |
| Legacy profiles | Both/Use-Cases-only browser preferences migrate to Gold; old environment source modes cannot enable Use Cases |
| Campaign names | Master labels preserved over ID-only rows; deterministic missing/conflict labels; master disagreements disclosed |
| Campaign/platform filters | Exact source-key matching; incompatible grains marked unavailable; exports cannot return unfiltered totals |
| Baseline measures | Unfiltered local spend, impressions, funding, contribution and experiment results preserved |
| Gold reads | All 113 sample objects readable; 91 source coverage records |
| Schema reference | Four active foundation locations: 377 definitions, 4,817 columns; historical fifth export retained in contract only |
| Permissions/transport | Viewer authorization, binding, SQL API parameter/chunk/error handling and cache isolation checked with mocks |
| Genie | Lifecycle, conversation isolation, sample answers, SQL/results and browser tab checked; no live Genie calls |
| Audit notebook | Python syntax checked; Spark SQL audit execution pending in Databricks |
| Physical table changes | None; app performs read-only analytics on existing Gold |

Browser checks cover all six reports, Gold explorer, metric details, campaign names, campaign/platform scope, date filtering, saved/reset filters, unavailable results, schema, lineage, dictionary, table pagination/search/export, Gold-only connection settings, mobile navigation and Genie. Screenshots from the current tests are in artifacts, including gold-campaign-platform-filters.png. Older use-cases-explorer.png is historical evidence of the previous version and is not the current UI.

Known local test baselines: vendor USD delivery cost 790,179.109988; native impressions 56,797,673; native clicks 1,729,617; funded banking accounts 282; observed contribution proxy USD 105,265.94; experiment units 480 with 81 conversions. Fixture values are not fixed expected live outputs. Some ancillary sample fields are simplified.

The Vite build emits a bundle-size advisory (approximately 918 KB uncompressed / 304 KB gzipped). Build passes; initial-load and warehouse latency require workspace measurement. Local testing does not certify Spark execution, approved campaign crosswalks, actual Gold row integrity, Genie curation, quotas or business KPI approval. Run the read-only Gold audit and workspace acceptance checks after redeploying this version.
