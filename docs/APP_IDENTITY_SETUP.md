# Resolve warehouse 403 with explicit app authorization

The previous deployed package always sent the viewer's forwarded token to SQL. Attaching sql-warehouse grants the **app service principal** access; it does not grant the viewer SQL scopes or warehouse access. A 403 on SELECT 1 occurs before table access, so reducing schema size cannot fix that authentication failure.

The updated app.yaml explicitly sets **SQL_AUTH_MODE=app** and **GENIE_AUTH_MODE=app**, using the Databricks SDK's OAuth M2M provider with platform-injected app credentials. Viewers need only Databricks App Can Use and sign-in; the developer configures resources/data once. It never uses a personal token, requests secrets from a viewer, or retries a rejected user request as another identity. Optional user modes remain available for individual permissions. Changing modes requires a deployment restart.

## Existing app: one-time setup

1. Keep the existing warehouse attached with resource key sql-warehouse and Can use or your existing Can manage grant.
2. Open **Databricks App -> Authorization** and copy the app service principal's **application/client ID**. This public ID is not a token, password, or secret.
3. As the owner of source-data.app_gold, run [grant_app_gold_read_access.sql](grant_app_gold_read_access.sql) in SQL Editor, replacing APP_SERVICE_PRINCIPAL_APPLICATION_ID. It grants only USE CATALOG, USE SCHEMA and SELECT. It creates no tables and does not republish data.
4. Redeploy the corrected package into this same app. Databricks automatically supplies DATABRICKS_HOST, DATABRICKS_CLIENT_ID and DATABRICKS_CLIENT_SECRET. Do not paste these credentials into the browser or app.yaml. app.yaml binds the warehouse ID through valueFrom.
5. Open the app and Verify & connect. Its configured dataset is source-data.app_gold. The connection dialog shows **Shared app access** and locks the schema to deployment settings. Existing browser location preferences are ignored in app mode.

All approved users of the app share the data permissions granted to its service principal. User-specific Unity Catalog row/column policies are not evaluated as each viewer. This mode is intended for the dedicated shared 30-table POC dataset. Grant CAN USE on the app only to its intended audience. App mode restricts record/table routes to the 30-table allowlist, fixes the catalog/schema in server configuration, and limits live column browsing to that same allowlist and namespace.

For deployments that need user-level policies, set SQL_AUTH_MODE=user and redeploy. Enable/consent to the sql user scope and grant viewers warehouse CAN USE plus their intended catalog/schema/table access. There is no automatic identity fallback in either mode.

## Automated owner setup

The updated deploy.ps1 runs this setup after bundle resource creation and before app startup. Install requirements.txt in the Python environment passed through -PythonExecutable and authenticate your existing Databricks CLI/SDK profile as an owner allowed to grant access.

For an app that already exists, run only the helper:

```powershell
python scripts/configure_app_read_access.py --app-name YOUR_APP_NAME --warehouse-id YOUR_EXISTING_WAREHOUSE_ID --profile DEFAULT
```

The helper discovers the app's service-principal application ID, verifies that source-data.app_gold contains exactly the 30 app tables, then issues the three read grants. It runs with your owner profile, outside the app runtime. It does not grant MODIFY, CREATE TABLE or catalog-wide SELECT. Warehouse CAN USE remains the attached resource's grant. No data or secrets are copied.

## Verify the running version

Open /api/runtime-config on the deployed app. The new build is **2026-11-23-share-link-access**; sql_auth_mode and genie_auth_mode should both be app. The endpoint exposes credential-presence booleans only. It does not return IDs, credentials, tokens or environment dumps.

A later app-mode 403 names app-principal grants and includes the structured Databricks error code with sensitive values redacted. If the warehouse probe succeeds but Gold inventories fail, check the three schema grants. Changing the catalog or table count is not the response to a failed pre-source warehouse probe.

Ask Genie uses the app principal by explicit configuration. The attached genie-space Can run grant and app principal's data grants are required once. Private signed browser/account sessions bind each conversation, follow-up and poll; users cannot reuse each other's conversation keys through the app. GENIE_AUTH_MODE=user is optional and requires the viewer's own scopes/consent and data privileges. Neither mode falls back to the other.

Verified locally with mocked OAuth/SQL responses and the 30-table sample. No live principal grants, OAuth token exchange or Databricks deployment was performed by this build process.

Official references: [app versus user authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth), [warehouse resource grants](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/sql-warehouse).
