# Developer setup and share-link access

The configured workflow matches the two supplied Databricks UI screenshots:

1. The developer attaches the SQL warehouse as sql-warehouse with Can use and the Genie Agent as genie-space with Can run.
2. The owner grants the app's service principal read access to source-data.app_gold once. This is separate from warehouse/Genie resource grants; use the existing setup SQL or owner helper.
3. The developer uses Databricks App -> Share, selects approved users/groups, grants Can Use, saves and sends the app URL.
4. Viewers sign in through Databricks and use the app. The default SQL_AUTH_MODE=app and GENIE_AUTH_MODE=app use managed app OAuth for both dashboards and Genie. Viewers do not need personal warehouse, table, or Genie grants for these shared app calls and do not need sql/genie delegated user scopes.

The bundle now declares no delegated data scopes. For an existing manually created app using both app modes, remove previously requested sql/genie delegated scopes in its Databricks user-authorization settings so viewers are not asked for unneeded data consent. The code does not require delegated tokens in app mode. App CAN USE is still enforced by Databricks; viewers sign in. The URL is not anonymous/public access. The screenshot's All workspace users -> Can Use grant includes the entire workspace; remove that group in Share if access should be limited to named people. This package does not modify your app sharing ACLs automatically.

All approved app users see the shared dataset. To use individual Unity Catalog policies, select SQL_AUTH_MODE=user and/or GENIE_AUTH_MODE=user, add the required delegated scopes and configure that user's privileges. The two modes are explicit; failed requests never switch identities.

## Genie conversations

The app principal owns Genie API conversations, so this app enforces browser/account isolation itself. An HttpOnly, Secure, SameSite=Lax signed cookie establishes a private browser session. Conversation authorization proofs include that session, the forwarded Databricks account identity when present, the configured Genie Agent, conversation ID and authorization mode. A different browser or account cannot reuse a captured conversation key through the app endpoints. No conversation listing or cross-user history endpoint is exposed.

The cookie contains a random signed session ID, never OAuth credentials. No new catalog tables are created. Session/signing keys are process-local: after an app restart or expired cookie, start a new Genie conversation. Administrators retain the platform's administrative access; browser isolation is between app users. Curate the attached Genie Agent on the intended app_gold tables and keep the app principal's source privileges limited to that dataset.

## Platform and More filters

- Platform choices load from accessible vendor delivery and synthetic campaign/platform marts; Product and Market choices come from the retained banking marts. Currency and Plan choices are read from their actual Gold columns. No live choices come from the uploaded HTML example or the offline sample.
- Each control has an available/empty/unavailable status and source/error details. Missing choices are explained and disabled; Currency and Plan never render as an unexplained blank selector. Existing selected values absent from refreshed choices are explicitly labeled as not loaded rather than silently removed.
- Refresh data reloads dropdown choices as well as reports. A failed metadata refresh preserves prior choices and selected filters and displays an error. It does not replace live report data with sample values.
- Campaign, Platform, Product and Market filters require matching keys in each dataset. A dataset without the selected key becomes unavailable instead of displaying its unfiltered overall total. Counts/costs are not reassigned through guessed joins.
- Currency preserves recorded units and does not convert money. Plan version applies to sales-target datasets and always uses one version. The automatic default follows the backend's descending plan-name order; select a specific plan when business approval requires it.

Local checks cover option failures/recovery, explicit plan/product/market filtering, private Genie follow-ups and shared OAuth. Final Databricks sharing, resource/data grants and live option values still require workspace execution.

References: [Databricks app sharing](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/permissions), [Genie resource grants](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/genie).
