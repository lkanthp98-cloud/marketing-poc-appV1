# Deploy the explorer-aligned Marketing Intelligence app

**Genie revision:** Follow [Genie setup](GENIE_SETUP.md) for automatic creation with warehouse + Genie resource attachments using `deploy.ps1`, or attach both resource keys manually in the UI. The current `app.yaml` references **genie-space** as well as **sql-warehouse**. Enable **sql** and **genie** user authorization scopes. The original SQL-only instructions below need these additions.

This package contains the app source and compiled frontend. No Databricks deployment or live account access has been performed by Codex.

## Prepare the workspace

The app is aligned to the uploaded explorer exports showing **113 Gold tables** and **30 Use Cases tables**, including metadata. The business pages use 28 published primary Use Cases datasets. They require the advanced 29-mart Gold contract represented in those exports. The separately supplied 17-mart Gold notebook does not produce every advanced input; select a complete compatible publication rather than replacing missing business values with sample data.

Confirm the Gold and Use Cases notebooks completed successfully. Defaults are:

| Purpose | Catalog | Schema |
|---|---|---|
| Marketing analytics | `source-data` | `usecases` |
| Gold explorer, shared dimensions and definitions | `media-poc` | `gold` |
| Source schema inspection | `media-poc` | `bronze`, `silver`, `model` |

The Use Cases schema name from the export is **`usecases`**, with no underscore. The mapping in `dashboard-data-mapping.csv` records every dashboard input and its Gold reference.

## Deploy

1. Extract `marketing-analytics-databricks.zip` into a clean directory. Upload/sync the extracted contents to one Databricks Workspace folder. `app.yaml`, `start.py`, `requirements.txt` and `package.json` must be at the selected app source root.
2. Create a Databricks App using this source folder.
3. Add a SQL warehouse resource, using resource key **`sql-warehouse`** and **Can use** permission. The warehouse ID is supplied through `valueFrom` in `app.yaml`. See [Databricks SQL warehouse resources](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/sql-warehouse).
4. Attach your Genie space with resource key **genie-space** and **Can run** permission. Enable **User authorization** and add **sql** and **genie** scopes. Users consent when opening the app; queries use their forwarded user token and Unity Catalog permissions. See [Databricks authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth).
5. Grant intended viewers app access, warehouse access, `USE CATALOG`, `USE SCHEMA` and `SELECT` on the required Gold/Use Cases tables. All schemas only displays the live column metadata visible to that identity. Bronze/Silver/Model record data is not queried by that metadata view.
6. Keep `DATA_MODE=live`. The four catalog/schema defaults above are already in `app.yaml`; change them if your publication locations differ. Databricks supplies host and app port environment variables.
7. Deploy and wait for the app build/start to finish. The app serves the React frontend and FastAPI API through `python start.py`.
8. Open the app. Use the top-right **Connection settings** button to select compatible Gold and Use Cases catalogs/schemas. The same control appears on the initial connection-error screen when defaults cannot be opened.

**Verify & connect** checks access to published manifests, the Use Cases datasets' recorded Gold locations, and the columns required by every dashboard. A successful selection is saved in a secure HttpOnly cookie for that browser. It changes no tables and grants no new permissions. The SQL warehouse remains the Databricks App resource, not a browser-supplied server. A different user/browser retains its own connection settings.

## Accept the live app

- Confirm business-page sources are `source-data.usecases.*` (or your verified selected namespace), and Gold explorer sources use the selected Gold namespace.
- Reconcile each KPI and chart against the same Use Cases table and Gold snapshot, with identical filters and reporting populations.
- Check publication IDs/readiness after a successful all-case pipeline run; avoid consuming partial multi-table publications.
- Test a date range, campaign, platform, native currency and one sales-plan version. Validate a zero-denominator or empty result.
- Open **Gold Data Explorer → Use case tables**, inspect column types and download filtered records. Then switch to **Gold tables** and inspect the Gold source independently.
- Open **All schemas**. Live metadata comes from `information_schema.columns` under the selected Gold catalog's `bronze`, `silver`, `model` and configured Gold schemas, plus the selected Use Cases location. It is not the packaged CSV snapshot.
- Verify a second user with different permissions, warehouse startup time, page response time and mobile layout.

Live mode has no sample-data fallback. Missing grants, incompatible publications or failed warehouse requests display errors. The app does not create tables, views, quarantine storage or other Unity Catalog objects, so it adds no table slots to the Free Edition budget. Compute/runtime limits still apply.

## Local sample review

Create a Python environment, install `requirements-dev.txt`, run `npm.cmd ci` and `npm.cmd run build`, set `DATA_MODE=preview`, then run `python start.py`. Open `http://localhost:8000`.

The included sample data is independently derived from the supplied synthetic source CSVs. It is not a download of live Gold/Use Cases contents. Temporary local SQLite views project the exported Use Cases column contract over those sample aggregates; ancillary attributes unavailable in the simplified fixture remain NULL. The app does not change live NULL handling. The All schemas reference preserves all 407 table definitions and 5,315 columns from the five uploaded explorer files. Live connection editing is disabled while in sample mode.
