# Deploy the Gold-backed marketing app

1. Run Bronze -> Silver -> DQX pass rows into Model -> Gold, then run `08_publish_app_gold_subset.ipynb` to publish the dedicated `app_gold` schema. See [subset publication](APP_GOLD_SUBSET.md). A separate Use Cases publisher is not needed. The initial app subset requires 30 additional table slots.
2. Extract the current `marketing-analytics-databricks.zip`. Select its root directory as the app source; it contains `app.yaml`, `requirements.txt`, `start.py` and the compiled UI.
3. Attach your SQL warehouse with resource key `sql-warehouse` (CAN USE). `app.yaml` maps that resource to DATABRICKS_WAREHOUSE_ID. Databricks supplies DATABRICKS_HOST; schemeless workspace hostnames are accepted.
4. Attach the desired Genie space with resource key `genie-space` (CAN RUN). Curate its datasets on Gold. Enable app user authorization scopes `sql` and `genie`; viewers must consent again after scope changes.
5. Grant viewers app access, warehouse CAN USE and the required Gold USE CATALOG, USE SCHEMA and SELECT privileges. This app queries using each viewer's forwarded token; resource grants to its service principal alone do not grant viewer data access.
6. Keep DATA_MODE=live. Configure GOLD_CATALOG/GOLD_SCHEMA in `app.yaml` (deployment defaults `source-data.app_gold`). No Use Cases environment variables or schema grants are required. Redeploy after changing code or resource bindings. Update existing browser connection preferences to the new schema.
7. In the app, Connection settings verifies the warehouse and Gold manifests and saves the selected Gold location in an HttpOnly browser cookie. Data permissions/columns are checked per visual; a successful manifest check does not certify every dataset or KPI.

The included `databricks.yml` and `deploy.ps1` can bind an existing warehouse and Genie space automatically during bundle deployment. See [Genie setup](GENIE_SETUP.md) for the CLI command and scope details.

The uploaded source Gold contract contains 29 marts, 78 entities and six metadata objects (113 total). The app publisher retains 23 marts, dim_campaign and six narrowed metadata tables (30 total). A smaller publication can connect when its Gold manifests are available; absent/inaccessible datasets produce unavailable visuals. The app does not fabricate values. Live schema browsing now reads authorized column metadata only in the selected app schema.

## Workspace acceptance

- Confirm business-page source labels and explorer data use the selected Gold namespace and the connection badge says Databricks Gold.
- Check a known campaign shows its master name, and its enterprise key filters the appropriate marts. Unresolved native vendor spend can remain unattributed.
- Reconcile each metric with its Gold table, date role, currency and reporting population. Campaign/platform selections must not preserve an unrelated overall total.
- Run the read-only [campaign/grain audit](../notebooks/07_gold_campaign_filter_integrity_audit.py) against live Gold. Review missing names, duplicate keys and unresolved mappings separately.
- Verify viewer permissions, Genie, warehouse response time, downloads and mobile layout. Local sample tests are not live workspace acceptance.

Local preview is an independent synthetic CSV-derived SQLite fixture, not a downloaded Gold snapshot. Deployed live mode never falls back to it, and the app creates no new tables in any mode.
