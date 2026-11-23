# Publish the 30-table app schema

Run `notebooks/08_publish_app_gold_subset.ipynb` in Databricks after the Gold notebook completes. The equivalent `.py` is a Databricks source notebook; import either format. No local Python module or app package import is required inside Databricks.

Default flow: **Bronze -> Silver -> Model -> Gold -> app_gold -> App**. DQX pass filtering remains within your existing Model notebook. There is no separate Use Cases publisher step for this app.

## Configuration and execution

| Widget | Default | Meaning |
|---|---|---|
| source_catalog / source_schema | media-poc / gold | Existing completed Gold publication |
| target_catalog / target_schema | source-data / app_gold | Dedicated app destination; catalog must already exist |
| object_budget | 450 | Conservative workspace object budget, capped at the user-reported ceiling of 500 |
| extra_counted_objects | 0 | Add other known objects included in your platform quota but absent from the visible inventory |
| run_mode | publish | Use plan for preflight without schema/table creation |

Run all cells with a principal that can read the 30 selected source tables, inspect their Delta history, create a schema/tables in the destination and replace its own prior publication. Stop Gold refreshes and pause the app during publication. Refreshes are sequential across tables, not an atomic multi-table release. Failed runs must be investigated and rerun successfully before reopening the app.

On success, the notebook prints **SUCCESS: exactly 30 tables published and reconciled** and the app connection values. Set the app's **Gold catalog = source-data**, **Gold schema = app_gold**. Deployment `app.yaml` uses this location by default. Existing browsers retain their saved location until changed in Connection settings. If the tables are already published there, connect to them directly; no additional copy or publication run is needed just to use the app.

The first run creates 30 additional managed Delta tables. It does not reduce the workspace total or remove the original Gold objects. Reruns replace the same 30 publisher-owned targets, without DROP/DELETE or persistent staging tables. Source and target must differ, and a destination containing unrelated objects is rejected. The publisher will not overwrite unmarked tables or unrelated existing app data.

## What is written

- 23 marts: the exact union of dashboard, supporting-record, date-range and platform-choice dependencies in the current app.
- One dimension: dim_campaign, used for campaign names and enterprise filter keys.
- Six metadata tables: gold_mart_catalog, gold_entity_catalog, gold_source_coverage, gold_kpi_dictionary, gold_use_case_readiness and gold_use_case_tables.

Business tables retain all selected Gold rows and column types, including native money fields and unresolved campaign mappings. Each source is pinned to a Delta version, and destination properties record its source, version, publication ID and publisher owner. Schema/data equality is checked for every destination using bidirectional EXCEPT ALL semantics; this preserves duplicate multiplicity as well as values. The notebook rejects null/duplicate master campaign keys before writes and checks that Gold versions have not changed during the run.

Metadata is deliberately transformed:

- Mart inventory contains exactly 23 rows and recomputed row counts; entity inventory contains only dim_campaign.
- Source coverage points only to copied tables. Existing fact/dimension dependency names from the Gold inventories are used to map documented lineage to retained marts. Upstream source row counts and selected-column references are retained. Sources without a documented dependency into this subset are omitted, so this count can be smaller than 91.
- Use-case table references and reporting-mart arrays exclude uncopied objects. Readiness preserves existing business limitations and explicitly lists excluded marts; it does not imply that all extended requirements are complete.
- KPI policies are retained as the existing governed dictionary. A dictionary definition alone is not a claim that its KPI is implemented by the app.

The app's inventory will show **23 marts + 1 dimension + 6 metadata tables = 30**. Live schema browsing now reads only the selected app schema, even if the viewer can see other schemas. The local preview remains the original source-derived fixture and reference export; the new publication is exercised through a separate simulated 30-table live namespace in tests.

## Capacity and permissions

The notebook counts visible active relations through system.information_schema.tables before making any destination writes. It includes new target tables and extra_counted_objects in the projection. The default budget of 450 leaves room below the workspace ceiling reported for this POC. The inventory is privilege-limited, does not independently discover every recoverable dropped object, and cannot prevent concurrent creations; it is not an authoritative quota counter. The platform's actual quota checks still apply. If the check fails, it writes nothing and performs no automatic cleanup. Complete capacity cleanup separately before rerunning.

For the default SQL_AUTH_MODE=app deployment, grant the app service principal USE CATALOG on source-data, USE SCHEMA on app_gold and SELECT on its tables. Warehouse CAN USE is granted through the attached resource. Approved app users share this dataset. If SQL_AUTH_MODE=user is selected, viewers instead need their own SQL scope/consent, warehouse CAN USE and intended data privileges. See [app identity setup](APP_IDENTITY_SETUP.md). Publisher permissions remain separate. CTAS does not duplicate source catalog grants or approval workflows.

For Ask Genie, curate the attached space on app_gold's 23 business marts and dim_campaign. Space datasets are managed independently from the app's connection selector. The six metadata tables need not be included in natural-language business analysis.

This smaller access boundary is useful but is not a proven fix for the previously reported telemetry configuration error. The publisher requires a live Databricks run; local tests do not execute Spark or certify platform quotas.

## Implementation references

- [Databricks CREATE TABLE / REPLACE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using)
- [Delta history and versioned reads](https://docs.databricks.com/aws/en/tables/history)
- [Information schema visibility](https://docs.databricks.com/aws/en/sql/language-manual/information-schema/tables)
