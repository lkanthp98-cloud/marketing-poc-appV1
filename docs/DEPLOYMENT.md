# Deploy the Gold-backed marketing app

1. Run Bronze -> Silver -> DQX pass rows into Model -> Gold, then run `08_publish_app_gold_subset.ipynb` to publish the dedicated `app_gold` schema. See [subset publication](APP_GOLD_SUBSET.md). A separate Use Cases publisher is not needed. The initial app subset requires 30 additional table slots.
2. Extract the current `marketing-analytics-databricks.zip`. Select its root directory as the app source; it contains `app.yaml`, `requirements.txt`, `start.py` and the compiled UI.
3. Attach your SQL warehouse with resource key `sql-warehouse` (CAN USE). `app.yaml` maps that resource to DATABRICKS_WAREHOUSE_ID. Databricks supplies DATABRICKS_HOST; schemeless workspace hostnames are accepted.
4. Attach the desired Genie Agent with resource key `genie-space` (CAN RUN) and curate its datasets on source-data.app_gold. The default GENIE_AUTH_MODE=app uses the app principal; viewers do not need delegated sql/genie scopes. Add scopes and viewer privileges only when deliberately selecting user modes.
5. Grant the app's existing service principal USE CATALOG, USE SCHEMA and SELECT on source-data.app_gold using [the read-only setup grants](grant_app_gold_read_access.sql). Both SQL_AUTH_MODE=app and GENIE_AUTH_MODE=app are defaults. Then use App -> Share to grant approved users/groups Can Use and send the URL. All approved app users share this dataset; review the All workspace users grant if only selected people should have access. See [sharing](SHARING_AND_FILTERS.md).
6. Keep DATA_MODE=live. Configure GOLD_CATALOG/GOLD_SCHEMA in `app.yaml` (defaults `source-data.app_gold`). Databricks injects the app's OAuth credentials. No Use Cases schema is required. Redeploy after changing code, SQL mode or resources. App mode fixes the namespace in server configuration and ignores old browser locations.
7. Connection settings explains the selected identity, tests the warehouse and reads the Gold manifests. Data permissions/columns are checked per visual; a successful manifest check does not certify every dataset or KPI. There is no automatic identity fallback.

The included `databricks.yml` and `deploy.ps1` bind existing warehouse/Genie resources. The script runs configure_app_read_access.py using an owner SDK profile to verify the 30-table destination and grant the app read access. Install requirements.txt in the Python environment supplied with -PythonExecutable. See [app identity setup](APP_IDENTITY_SETUP.md) and [Genie setup](GENIE_SETUP.md).

The uploaded source Gold contract contains 29 marts, 78 entities and six metadata objects (113 total). The app publisher retains 23 marts, dim_campaign and six narrowed metadata tables (30 total). A smaller publication can connect when its Gold manifests are available; absent/inaccessible datasets produce unavailable visuals. The app does not fabricate values. Live schema browsing now reads authorized column metadata only in the selected app schema.

## Workspace acceptance

- Confirm business-page source labels and explorer data use the selected Gold namespace and the connection badge says Databricks Gold.
- Check a known campaign shows its master name, and its enterprise key filters the appropriate marts. Unresolved native vendor spend can remain unattributed.
- Reconcile each metric with its Gold table, date role, currency and reporting population. Campaign/platform selections must not preserve an unrelated overall total.
- Run the read-only [campaign/grain audit](../notebooks/07_gold_campaign_filter_integrity_audit.py) against live Gold. Review missing names, duplicate keys and unresolved mappings separately.
- Verify viewer permissions, Genie, warehouse response time, downloads and mobile layout. Local sample tests are not live workspace acceptance.

Local preview is an independent synthetic CSV-derived SQLite fixture, not a downloaded Gold snapshot. Deployed live mode never falls back to it, and the app creates no new tables in any mode.
