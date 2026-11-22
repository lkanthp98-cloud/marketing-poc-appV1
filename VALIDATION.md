# Local validation record

Validated 22 November 2026 against the supplied synthetic source files and all five uploaded explorer CSV contracts. Live account access and deployment remain unverified.

| Check | Result |
|---|---|
| TypeScript strict compile and production Vite build | Passed |
| Backend contract tests | 45 passed |
| Host/resource regression | Scheme-less/HTTPS hosts, warehouse aliases, isolated errors, SQL/Genie transport and safe diagnostics passed |
| Playwright browser scenarios | 7 passed |
| Independent source modes | Gold-only, Use-Cases-only and both passed; disabled sources were not queried |
| Separate single-source browser instances | Both Gold-only and Use-Cases-only loaded all six dashboards and their enabled explorer |
| Permission diagnostics | Warehouse probe runs before any source verification; later failures name the selected layer |
| Genie lifecycle/result parsing and conversation isolation | Mocked API checks passed; no live Genie calls |
| Genie sample UI | Guided CSV-derived answers, SQL, results, tab navigation and reset passed |
| Automatic attachment deployment helper | PowerShell syntax checked; authenticated bundle deployment pending |
| Published object inventory in preview | 113: 29 marts + 78 entities + 6 metadata tables |
| Gold table preview reads | All 113 successful |
| Use Cases table preview reads | All 30 successful; 28 datasets and 2 metadata tables |
| Schema export reference | 407 table definitions and 5,315 associated columns across 5 locations |
| Dashboard source/column alignment | All 42 elements matched to exported Use Cases datasets |
| Default analytics namespace | source-data.usecases |
| Default Gold namespace | media-poc.gold |
| Per-browser live connection and request/worker isolation | Mocked warehouse tests passed |
| Source coverage | All 91 feeds represented |
| Accepted source fixture rows | 68,372; 94 rows excluded by current DQ rules |
| Browser pages | Six analytics pages + Gold Data Explorer |
| Mobile | Navigation and page overflow checked at 390 × 844 |
| Desktop | Charts and controls checked at 1440 × 1050 |
| Warehouse adapter | Parameter binding, chunk parsing, failures, authorization and viewer cache isolation mocked |
| Live workspace connection and deployment | Pending workspace execution |

The browser scenarios cover page navigation, charts, metric details, filters, saved views, empty states, both Gold and Use Cases discovery, schema, lineage, KPI definitions, pagination, CSV download, all-schema search and the connection dialog in sample mode. Desktop and mobile screenshots are included under `artifacts/`. A mocked live namespace test confirms business marts resolve to Use Cases, while Gold explorer data resolves to Gold. A separate mocked connection test validates browser-specific catalog/schema selection and worker-thread isolation. No test used a live Databricks warehouse.

Visual review verified the experiment interval includes both bounds and crosses zero. The table displays its absolute lift and confidence bounds in percentage points, with a separate relative lift and four-decimal p-value.

Verified fixture totals: vendor native USD cost 790,179.109988; impressions 56,797,673; reported clicks 1,729,617; funded banking accounts 282; synthetic banking net contribution 105,265.94 USD; experiment eligible units 480 and converted units 81.

The preview is an independent local reproduction derived from source CSVs, not a workspace data export. Some source/model audit fields are simplified. Local Use Cases views project the exported column contract; ancillary fixture fields not available locally remain NULL. Successful local checks do not certify Spark execution, live mapping approvals, financial definitions or production runtime compatibility. Complete the workspace acceptance checks in `docs/DEPLOYMENT.md` after publishing compatible Gold and Use Cases outputs and configuring app authorization. The separately supplied 17-mart Gold notebook is a smaller contract than the 113-table explorer export used for this app.

The production build emits a bundle-size advisory for the ECharts/React bundle (approximately 905 KB uncompressed, 300 KB gzipped). The build succeeds; initial-load performance should be measured in the workspace.
