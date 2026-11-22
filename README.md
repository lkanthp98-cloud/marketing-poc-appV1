# Marketing Intelligence

**Independent source connections:** Connection Settings now supports **Gold only**, **Use Cases only**, or **both**. Disabled sources are never checked or queried. Gold-only dashboards read registered Gold marts; Use-Cases-only dashboards do not require Gold dimensions or metadata. Missing/inaccessible visuals are labeled unavailable. See [source modes and permission troubleshooting](docs/SOURCE_CONNECTIONS.md). Current checks: **45 backend tests and 7 browser scenarios passed**, including separate single-source app instances.

**Host/resource fix:** The app now normalizes scheme-less `DATABRICKS_HOST` values to HTTPS for SQL and Genie. It distinguishes host configuration errors from a missing warehouse binding. Redeploy this updated source into the existing app. See [runtime troubleshooting](docs/RUNTIME_TROUBLESHOOTING.md).

**Genie update:** The app now includes **Ask Genie**, with questions, follow-ups, SQL and result tables. [Genie setup and automatic attachment](docs/GENIE_SETUP.md) explains the included `databricks.yml` and `deploy.ps1`. The bundle creates the app with warehouse and Genie resource bindings after you supply their existing IDs. UI-created apps must attach both resources explicitly. User authorization now needs **sql** and **genie** scopes.

A combined marketing analytics app, Gold/Use Cases Data Explorer and schema browser, built for Databricks Apps. Business pages read the published Use Cases datasets; Gold supplies shared dimensions, lineage and KPI definitions. React and Apache ECharts provide the interface; FastAPI queries Databricks SQL using the signed-in viewer's authorization.

This revision is aligned to **all five uploaded explorer CSVs**: 407 table definitions and 5,315 associated columns. Business data defaults to **`source-data.usecases`**; Gold defaults to **`media-poc.gold`**. See [deployment instructions](docs/DEPLOYMENT.md) and [schema alignment](docs/SCHEMA_ALIGNMENT.md). Live data access and deployment still require workspace validation.

## What is included

| Page | Available reporting |
|---|---|
| Executive Overview | Vendor investment, synthetic campaign leads, banking funded accounts and observed contribution |
| Campaign & Paid Media | Platform delivery cost, native impressions and clicks, weighted efficiency and synthetic campaign economics |
| Customer Acquisition | Banking application quality, first funded customers, synthetic submission cohorts and funnel |
| Digital & Offline | Website engagement, email deliveries and clicks, direct-mail job responses |
| Financial Performance | Signed relationship proxies, three separate cost representations and sales-plan attainment |
| Experiments & Brand | Configured experiment outcomes, nominal uncertainty intervals and individual survey cells |
| Gold Data Explorer | Gold: 113 objects; Use Cases: 30 objects; all-schema column reference across Bronze, Silver, Model, Gold and Use Cases |
| Ask Genie | Live text analytics over a curated Genie space; clearly labeled guided sample answers locally |

Global date, campaign, platform, product, market, currency and sales-plan controls apply where each table supports them. The interface includes source scope explanations, metric drawers, expandable charts, platform chart filtering, saved browser filter selections, searchable records, pagination, sorting, CSV downloads and responsive navigation. Explorer tabs provide data, schema, source lineage and the shared KPI dictionary.

All 91 source feeds remain discoverable through Gold coverage and conformed entities. The business pages implement the supported metrics from the existing Gold foundation. They do not claim that all extended requirements across the ten use cases are complete. TV/OOH details, referral/call records, supplemental e-commerce and other domain tables are available through the explorer; their specialized dashboards are future additions.

## Run locally

Use Python 3.11+ and Node 22.12+.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm.cmd ci
npm.cmd run build
$env:DATA_MODE = 'preview'
.venv\Scripts\python.exe start.py
```

Open http://localhost:8000. On Linux/macOS use `.venv/bin/python`, `npm`, and `export DATA_MODE=preview`.

The supplied `data/preview.db.gz` is a read-only, offline preview derived from the source CSVs using the current Silver column selection and DQ pass rules: 68,372 accepted rows from 68,466 inputs. It is labeled throughout the UI. It is not a downloaded Databricks Gold snapshot. The preview builder independently reproduces the supported aggregates and selected model fields for local verification; actual Spark execution, workspace mapping approvals and financial acceptance remain separate validation steps. Regenerating it with `python -s scripts/build_preview.py` requires the original parent POC workspace, notebooks, source CSV folder and pipeline test helpers.

For frontend development, run the Python server and `npm run dev` in separate terminals. Vite proxies `/api` to port 8000.

## Deploy to Databricks Apps

1. Complete Bronze, Silver/02B, the merged DQX-pass-to-Model notebook, Gold and Use Cases publication. The supplied explorer exports show the earlier 29-mart Gold contract and 28 published primary Use Cases datasets. This app revision matches that exported contract, including its advanced tables; the separate 17-mart Gold notebook alone cannot supply those outputs.
2. Extract `marketing-analytics-databricks.zip` into a clean source directory and upload/sync its contents to a Databricks Workspace folder. Select that folder as the app source. `app.yaml`, `package.json`, `requirements.txt` and `start.py` must be at the selected source root.
3. Create a Databricks App. Add a SQL warehouse resource with resource key **`sql-warehouse`** and **Can use** permission. The warehouse ID is injected through the `valueFrom` reference in `app.yaml`.
4. Attach a Genie space with key **`genie-space`** and **Can run** permission. Enable **User authorization** with **`sql`** and **`genie`** scopes. The app reads the server-provided `x-forwarded-access-token` header. It never sends this token to the frontend or stores it in the browser. The bundle/script performs the resource declarations and scope configuration automatically when creating its managed app.
5. Give each intended viewer permission to use the app and warehouse, plus `USE CATALOG`, `USE SCHEMA` and `SELECT` on the required Gold and Use Cases objects. Unity Catalog evaluates each viewer's identity. No app-side campaign approvals or data writes are performed.
6. `app.yaml` includes `GOLD_CATALOG=media-poc`, `GOLD_SCHEMA=gold`, `USE_CASES_CATALOG=source-data` and `USE_CASES_SCHEMA=usecases`. Keep **`DATA_MODE=live`**. Databricks supplies `DATABRICKS_HOST` and `DATABRICKS_APP_PORT` automatically. After deployment, **Connection settings** lets a user verify and select compatible publication locations in their browser.
7. Deploy. The build installs Python and npm dependencies, runs `npm run build`, and starts `python start.py`. The Python process serves both the compiled frontend and API on the injected app port.
8. Open the deployed app as an authorized user, consent to the configured scopes, then perform the workspace checks below.

Optional CLI sync after authenticating with an existing Databricks CLI profile:

```powershell
databricks sync . /Workspace/Users/YOUR_EMAIL/marketing-analytics-app
databricks apps deploy YOUR_APP_NAME --source-code-path /Workspace/Users/YOUR_EMAIL/marketing-analytics-app
```

The ZIP excludes dependencies, virtual environments and local test output. It includes the frontend source and compiled files. The preview archive is included to support local review; deployed runtime explicitly rejects preview mode and never falls back to it after a live query failure.

### Workspace acceptance checks

- Confirm the top-right connection says **Databricks Use Cases** on business pages and **Databricks Gold** when exploring Gold.
- Check the catalog contains the current 29 marts, 78 entities and six metadata objects; inspect all 91 coverage records.
- Reconcile each KPI with the same Use Cases table, its Gold source, date role, currency and filter values. Local fixture totals below are not expected to stay fixed after source refreshes or campaign approvals.
- Select a resolved campaign and validate the approved mapping; keep unapproved vendor rows identifiable. A campaign filter can produce no vendor spend until approvals exist.
- Check two users with different Unity Catalog permissions. A missing authorization or table grant must show an access error.
- Verify warehouse startup, expected page response time, downloads and the final mobile layout in your workspace.

## Measurement contract

- Native vendor money remains in its labeled currency. The app filters one currency and does not sum across currencies or invent exchange rates.
- Platform delivery cost, invoices and GL costs remain separate. Observed synthetic banking contribution is a proxy, not audited revenue, incremental ROI or forecast LTV.
- Synthetic campaign cohorts, operational banking outcomes and vendor delivery are distinct populations. The executive cards do not imply a joined attribution funnel.
- Approved campaign keys filter vendor data. Proposed/unapproved matches never become approved through the app.
- Rates use ratios of sums. Zero or absent denominators display an unavailable value.
- Monthly marts include the selected calendar months. Previous-period comparison uses an equal count of nonoverlapping whole months; daily marts use an equal day count. Campaign cohorts use campaign flight start; experiment metrics retain their configured assignment windows. Views without a compatible period report the unsupported filter.
- Target actuals are filtered to one plan version. A plan selector affects tables that contain a plan version.
- Brand visuals show individual survey cells, without averaging unrelated waves or claiming causal lift.
- Detail exports include at most **10,000 filtered/searched rows**. Text values that could become spreadsheet formulas are escaped.

SQL identifiers and measures are controlled by the backend. Filter values are bound parameters. Gold/Use Cases record views use the published inventories; there is no arbitrary SQL editor. All schemas reads authorized live column metadata after deployment, and uploaded schema references in sample mode. Schema caches are isolated by viewer identity and namespace, expire after 60 seconds, and never cache query results or user tokens. API responses use `Cache-Control: no-store`. Connection preferences contain only catalog/schema names and are stored in a secure HttpOnly browser cookie; they do not grant data permissions or change other browsers' connections.

## Validation

```powershell
.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
npm.cmd run build
npm.cmd run test:ui
```

The browser checks require a running local server. Playwright uses installed Chrome on Windows when available; elsewhere install its Chromium browser with `npx playwright install chromium`, or set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`.

37 backend checks cover 113 Gold and 30 Use Cases reads, all five schema exports, reporting queries, filters, exports, authorization, mocked live routing, browser connections, caches, Genie conversations, host normalization and resource-binding diagnostics. Six browser scenarios cover the eight pages, charts, drawers, filters, both data layers, all-schema search, connection settings, downloads, mobile layout and guided Genie sample answers. The host/resource patch changes backend configuration handling only; the UI is unchanged. Live Genie APIs and bundle deployment still require workspace validation.

Known local fixture values: vendor USD delivery cost **790,179.109988**; native impressions **56,797,673**; native clicks **1,729,617**; funded banking accounts **282**; observed contribution proxy **105,265.94 USD**; experiment eligible units **480**, converted units **81**. Nominal experiment comparison is inconclusive and must not be presented as a significant winner.

No deployment or live Databricks execution was performed while building this package. Local runtime was Python 3.14 and Node 24; the default Databricks runtime documented at build time is Python 3.11 and Node 22. Workspace dependency installation and final execution require acceptance there.

## Files

- `backend/catalog.py`: governed dashboard queries and table/date roles.
- `backend/store.py`: SQL Statement Execution access and offline preview adapter.
- `backend/main.py`: authenticated API, filters, metadata, tables and exports.
- `frontend/src/`: React pages, charts, explorer and responsive styling.
- `app.yaml`: live Databricks runtime configuration.
- `data/preview.db.gz`: source-derived local review dataset.
- `artifacts/`: reviewed desktop and mobile screenshots.

## Databricks documentation

- [Deployment build sequence](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy)
- [Python and Node dependencies](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/dependencies)
- [SQL warehouse resource](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/sql-warehouse)
- [User authorization and SQL scopes](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth)
- [Runtime environment variables](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/system-env)
