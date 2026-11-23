# Host and attached-warehouse runtime fix

For the pre-source warehouse HTTP 403, see [app identity setup](APP_IDENTITY_SETUP.md). The updated deployment explicitly uses the managed app principal for dashboard SQL; the attached warehouse grant and schema grants must apply to that same identity. User SQL mode remains optional and does not fall back to app identity.

The old error, `Configure DATABRICKS_HOST and the sql-warehouse app resource`, combined two separate checks. It could appear even when the warehouse was correctly attached, because the original code required the host string to start with `https://`.

Databricks' [official Apps example](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/vector-search) explicitly handles DATABRICKS_HOST values without a scheme. This package now adds HTTPS to a bare workspace hostname and trims surrounding whitespace/trailing slashes. Both SQL and Genie use the normalized host. Missing and invalid host values, and missing warehouse IDs, have distinct messages. Explicit insecure HTTP URLs are not silently accepted.

## Redeploy the existing app

1. Extract the corrected ZIP and replace the existing app source with its contents. Keep `app.yaml` at the selected source root.
2. Keep the attached warehouse resource key **sql-warehouse**, with **Can use** permission. The existing `app.yaml` maps that resource through `valueFrom: sql-warehouse` to **DATABRICKS_WAREHOUSE_ID**. If a different resource key was chosen in the UI, change the matching `valueFrom` reference before deployment. See [warehouse resource configuration](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/sql-warehouse).
3. Redeploy the app from the corrected source. A running process does not pick up changed Python code/environment by editing a local ZIP.
4. Reopen the deployed app. Keep SQL and Genie user authorization/permissions configured as documented in GENIE_SETUP.md.

No app recreation or manual token configuration is needed for this code fix. Databricks supplies the workspace host in its managed app runtime. Attaching a resource and referencing its key in app.yaml are both necessary to inject the warehouse ID; the app does not select an unrelated warehouse or fall back to sample data.

The canonical warehouse variable is DATABRICKS_WAREHOUSE_ID. For compatibility with explicitly configured environments, the app also recognizes DATABRICKS_SQL_WAREHOUSE_ID and WAREHOUSE_ID, in that priority order. It prefers the canonical variable whenever non-empty.

## Safe diagnostics

Open `/api/runtime-config` on the deployed app. It reports configuration/credential-presence booleans, binding variable names, SQL mode and build identifier **2026-11-23-explicit-app-oauth**. It never returns hostnames, resource IDs, user tokens, client secrets or the full environment.

If `workspace_host_valid` and `warehouse_id_present` are both true, runtime binding checks have passed. Subsequent errors can concern authorization, warehouse readiness, tables or schemas and should be handled using their specific messages. This endpoint does not claim live query success.

The patch was verified with the offline backend checks, including HTTPS request construction with a scheme-less host and an attached warehouse ID. The reported workspace error has not been reproduced inside your live account, so the precise runtime values remain unverified.
