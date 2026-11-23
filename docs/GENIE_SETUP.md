# Shared Genie analytics and app-link access

The Ask Genie tab supports questions, follow-ups, generated SQL and result tables. The app displays Genie SQL and never replays it through its own SQL endpoint.

## Developer setup once

1. Curate a Genie Agent on the retained business marts and dim_campaign in source-data.app_gold. Configure its SQL warehouse, approved metric definitions and tested questions. Suggested sources include mart_vendor_media_daily, mart_demo_campaign_economics, mart_new_funded_customers_monthly, mart_sales_target_attainment_monthly, mart_demo_three_source_cost_reconciliation, mart_demo_experiment_variant and mart_brand_survey_wave.
2. Attach the warehouse to the Databricks app with key sql-warehouse and Can use. Attach the Genie Agent with key genie-space and Can run. These grants apply to the app service principal.
3. Grant that principal USE CATALOG, USE SCHEMA and SELECT on the app_gold dataset using the existing setup SQL or owner helper. Agent resource attachment alone does not grant data access.
4. Deploy with SQL_AUTH_MODE=app and GENIE_AUTH_MODE=app. Databricks supplies managed OAuth credentials; the bundle requests no delegated user data scopes.
5. In App -> Share, select approved users/groups and grant Can Use, then share the app link. Viewers sign in to Databricks. They do not need personal warehouse, table or Genie permissions for these shared app calls. Review any All workspace users grant if only named people should have access.

The Genie Agent owns its table selection and instructions. Dashboard filters and Connection settings do not alter the Agent. Include the intended dates, currency and reporting population in questions. Keep vendor delivery, demo cohorts and banking outcomes distinct. The attached Agent must reference the intended app_gold data and the app principal must be limited to that data. Use GENIE_SPACE_INSTRUCTIONS.txt as a business-context starting point and validate generated answers in the workspace.

## Private conversations under a shared principal

The Databricks Genie API sees the app principal as the conversation owner. This app binds every conversation key to a signed browser session, forwarded account identity when present, Agent, conversation ID and auth mode. A different browser/account cannot follow or poll another user's conversation through app endpoints, even with a captured conversation key. There is no history-list API for other users.

A random signed session cookie is HttpOnly, Secure and SameSite=Lax. It contains no OAuth credentials. Conversation text remains in browser memory during tab navigation and resets on a full reload. Session/signing keys are process-local; after a restart or expired cookie, use New conversation. Administrators keep the platform's administrative visibility.

## Optional individual permissions

GENIE_AUTH_MODE=user is available for deployments that require each user's Unity Catalog policies. That mode requires the forwarded user token, sql/genie scopes, consent and intended Agent/data access. SQL_AUTH_MODE can be configured separately. There is no automatic identity fallback after errors. User modes are not required for the requested shared-app-link workflow.

## Automatic attachment

The included databricks.yml declares the SQL warehouse and Genie resources. With an authenticated owner CLI/SDK profile and requirements.txt installed:

```powershell
.\deploy.ps1 -WarehouseId 'YOUR_WAREHOUSE_ID' -GenieSpaceId 'YOUR_GENIE_AGENT_ID' -AppName 'YOUR_APP_NAME' -Profile 'DEFAULT'
```

The script validates/deploys the bundle, verifies the 30-table destination, grants the app read access through the owner helper and starts the app. It does not create another warehouse, Genie Agent or catalog tables. -ValidateOnly checks the bundle without deployment. Existing manually created apps can keep their attachments and be redeployed from the corrected ZIP; use the one-time setup SQL if grants are missing.

## Local verification

Preview mode executes only the three guided sample questions on CSV-derived local data and labels them accordingly. Arbitrary sample prompts do not produce invented answers. Shared OAuth, account/browser isolation and API lifecycle are exercised with mocks; final live Genie answers, platform sharing and ACLs require workspace validation.

References: [Genie app resource](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/genie), [Genie Agents API](https://docs.databricks.com/aws/en/genie-agents/conversation-api), [Databricks app sharing](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/permissions).
