# Genie analytics and automatic resource attachment

The new **Ask Genie** tab supports natural-language questions, follow-up conversations, answer text, generated SQL and result tables. It polls asynchronous Genie processing, displays failures/expired results, and limits displayed results to 100 rows from the first available result chunk. SQL returned by Genie is shown as text; the app does not replay it through its SQL query endpoint.

Live Genie uses the signed-in viewer's forwarded token, not a shared service-principal fallback. Conversations are bound to the viewer/session and configured space. A new sign-in/token or app restart can require **New conversation**. Chat history stays in browser memory while navigating app tabs and resets on a full reload. No tokens are returned to the browser or stored with conversations.

## Prepare one Genie space

Create or select a curated marketing Genie space in the same workspace as the app. Use the existing published datasets from `media-poc.gold`, with approved KPI definitions. Suggested starting datasets:

- `mart_vendor_media_daily`
- `mart_demo_campaign_economics`
- `mart_new_funded_customers_monthly`
- `mart_sales_target_attainment_monthly`
- `mart_demo_three_source_cost_reconciliation`
- `mart_demo_experiment_variant`
- `mart_brand_survey_wave`

Add further datasets as needed for your business questions. Curate this space on Gold marts and conformed dimensions, including `dim_campaign` for campaign names. Do not add duplicate Use Cases publications. Put the relevant definitions from `GENIE_SPACE_INSTRUCTIONS.txt` into the space instructions. Its warehouse must be configured and viewers must have the necessary Genie, warehouse and table privileges.

The Genie space owns its dataset selection and business instructions. Dashboard Connection Settings and filters do not reconfigure that space. Include the desired dates, currency and population in questions. Curating a space improves answers but does not certify generated SQL or causal conclusions; review the SQL and its result before business use.

## Automatic attachment when creating the app

The included **databricks.yml** defines the app, resource bindings and authorization scopes:

| Resource key | Attachment | Permission |
|---|---|---|
| `sql-warehouse` | Your existing warehouse ID | `CAN_USE` |
| `genie-space` | Your existing Genie space ID | `CAN_RUN` |

`app.yaml` receives their IDs through `valueFrom`. The bundle declares user API scopes **sql** and **genie**. Catalog/schema defaults remain configured in `app.yaml`; viewer permissions on Unity Catalog data remain necessary. Resource bindings grant the app identity permissions and do not automatically grant every viewer access to data.

From the extracted app directory, with the current Databricks CLI installed and authenticated, run:

```powershell
.\deploy.ps1 -WarehouseId 'YOUR_WAREHOUSE_ID' -GenieSpaceId 'YOUR_GENIE_SPACE_ID' -AppName 'marketing-intelligence-genie' -Profile 'YOUR_CLI_PROFILE'
```

This validates the bundle, creates/updates the bundle-managed app with both resources attached, uploads the source, and starts the app. Supply the two workspace-specific IDs once; they cannot be inferred from column exports. Add `-ValidateOnly` to validate without deployment. The person deploying needs permission to create/manage the app and attach the selected resources.

Use a unique app name for a new bundle-managed deployment. For an existing manually created app, the UI route below updates its attachments without creating another app. This package does not create a Genie space or warehouse, assign viewer-wide table grants, or create new Unity Catalog tables. No deployment has been performed from this environment. The Databricks CLI was not installed here, so authenticated `bundle validate/deploy/run` still require workspace execution; the deployment script's PowerShell syntax was checked locally.

## UI creation or updating an existing app

Under **App resources**, attach the warehouse with key **sql-warehouse**, and the Genie space/agent with key **genie-space**, granting **Can use** and **Can run** respectively. Enable user authorization with both **sql** and **genie** scopes. Deploy this source folder. Uploading source containing `app.yaml` alone does not create those attachments; use the bundle/script for automatic attachment.

Each viewer needs access to the app, Genie space, applicable warehouse and underlying tables. When the scopes change, users may need to consent again. Keep **DATA_MODE=live**. If Genie is unavailable in your workspace or the resource is not configured, the app reports the failure rather than serving local sample answers.

## Local verification

In **DATA_MODE=preview**, the three suggested questions execute fixed, read-only queries on the CSV-derived local fixture. They are labeled **guided sample answers**, not live Genie responses. Arbitrary prompts do not produce fabricated answers. Open-ended language and contextual follow-ups require live Genie.

Local checks: 37 backend tests and 6 browser scenarios passed, along with the production frontend build. Six backend checks specifically cover the later host/resource configuration fix; the UI is unchanged by that patch. Genie start/follow-up/poll/result APIs were mocked; no real Genie space or live warehouse was queried. The two SQL/Genie attachments and OAuth scopes use the official documented bundle/resource fields, but final API compatibility, permissions, deployment and answer reconciliation must be checked in your workspace.

References: [Genie app resource](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/genie), [app resources in bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/resources#appresources), [bundle app deployment](https://docs.databricks.com/aws/en/dev-tools/bundles/apps-tutorial), [Genie conversation API](https://docs.databricks.com/api/genie/v1/genie-start-conversation).
