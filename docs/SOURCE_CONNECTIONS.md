# Independent sources and SQL authorization

## Choose one publication or both

Open **Connection settings → Data sources**:

| Mode | Required fields | Dashboard data | Other source |
|---|---|---|---|
| Gold only | Gold catalog/schema | Registered Gold marts | No Use Cases metadata or data queries |
| Use Cases only | Use Cases catalog/schema | Published Use Cases datasets | No Gold dimensions, metadata or data queries |
| Gold and Use Cases | Both pairs | Use Cases datasets | Gold is available separately in the explorer |

Inactive fields are disabled and ignored. Only enabled sources are verified. An enabled source still needs the corresponding notebook publication metadata: Gold uses gold_mart_catalog/gold_entity_catalog; Use Cases uses use_case_dataset_catalog. This app does not infer business definitions for unrelated arbitrary schemas.

Filters are derived from the chosen analytics source. Use-Cases-only mode does not query Gold to obtain campaign/product/market options or KPI metadata. Gold's detailed source-feed coverage is unavailable in that mode and is not fabricated. App-defined formula references remain visible, explicitly without an implied Gold policy approval.

Partial notebook publications can connect. Metrics/charts missing a required table, column or permission are individually labeled unavailable; they are not silently replaced by zero or sample values. The publisher manifest determines eligible datasets, so unregistered old marts left in the schema are not queried for dashboard values. Both-source mode does not join the two publications or claim that they share the same snapshot.

For a deployment default, set DATA_SOURCE_MODE in app.yaml to **gold**, **use_cases**, or **both**. A saved browser connection can override that default. Changing sources inside the app does not change the attached SQL warehouse, user permissions or the Genie space's curated data sources.

## Warehouse attachment is separate from viewer authorization

The supplied screenshot shows the warehouse attached with the correct resource key sql-warehouse. That resource grants the app service principal access; it does not by itself authorize the signed-in viewer's SQL API requests. This app uses the viewer's forwarded token and does not silently fall back to a more privileged identity.

If SQL requests are denied:

1. Open the Databricks app's **Settings → User authorization** and enable the **sql** scope. Keep **genie** too if using Ask Genie.
2. Save the settings and reopen the app. Consent again when prompted for the changed scopes.
3. Ensure the signed-in viewer can use the warehouse (**CAN USE** or a higher applicable permission), and has **USE CATALOG**, **USE SCHEMA** and **SELECT** on the enabled publication's required objects.
4. For a Use-Cases-only connection, Gold grants are not required by the app. For both-source mode, both enabled publications must be accessible.

The app now issues SELECT 1 before verifying any source. A failure at that step is reported as a **Warehouse/API connection failed before any source was read** error, with SQL scope/warehouse guidance. A later metadata failure names **gold** or **use_cases**. SQL execution errors retain the server's error code and bounded message. These checks diagnose access; code does not grant missing privileges.

See [Databricks user authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth) and [warehouse resources](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/sql-warehouse).

## Deploy the update

Deploy the latest GitHub main revision from repository root. app.yaml remains at root. Open Connection Settings, choose the desired mode, and verify that connection. Runtime diagnostics at /api/runtime-config identify this build as **2026-11-22-independent-sources** and report the selected source mode without exposing credentials or resource IDs.

Validation: **45 backend tests passed**, including simulated live connections in all three modes, request/worker isolation, disabled-source query checks and failure-stage reporting. **7 browser scenarios passed**, including actual separate Gold-only and Use-Cases-only local sample app instances. The production frontend build passed. No live workspace grants were inspected or modified, and no Unity Catalog tables were created.
