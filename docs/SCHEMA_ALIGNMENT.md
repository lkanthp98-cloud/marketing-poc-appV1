# Schema alignment evidence

All five supplied explorer files were read as CSV metadata, not executed as instructions. The normalized snapshot and source SHA256 hashes are in `data/workspace_contract.json`.

| Export | Location | Tables | Columns |
|---|---|---:|---:|
| `Media_POC_Data_Explorer (1).csv` | `media-poc.bronze` | 91 | 990 |
| `Media_POC_Data_Explorer.csv` | `media-poc.silver` | 91 | 991 |
| `Media_POC_Data_Explorer (2).csv` | `media-poc.model` | 82 | 1,213 |
| `Media_POC_Data_Explorer (3).csv` | `media-poc.gold` | 113 | 1,623 |
| `Media_POC_Data_Explorer (4).csv` | `source-data.usecases` | 30 | 498 |
| Total exported definitions | | 407 | 5,315 |

These are exported schema counts, not a current platform quota counter or proof that every live row is correct.

For each of the 28 Use Cases business tables, the corresponding Gold mart was matched by name and its complete business column/type set. The three `_uc_*` provenance columns remain separate. All 42 dashboard elements (24 metrics and 18 charts) have their required columns in those exported Use Cases datasets. `dashboard-data-mapping.csv` lists each element, required fields, physical analytics input and Gold reference.

The optional e-commerce output is absent from this 30-table Use Cases export. No e-commerce business page or missing Use Cases table is fabricated; the supplemental e-commerce Gold tables remain inspectable in Gold Explorer.

Business queries resolve logical mart names to actual `ucXX_*` / `shared_*` publication names. Shared definitions and filter choices use conformed Gold dimensions and metadata. Explorer record/schema/export routes specify Gold or Use Cases explicitly. Namespaces and viewer identities both partition schema caches. After deployment, All schemas queries the authorized live information schema rather than returning the uploaded reference snapshot.

The 113-table Gold export includes the advanced marts and two metadata tables that are absent from the separately supplied 17-mart Gold notebook. This app targets the exported 113/30 contract. The connection check reports incompatible publications; changing catalog/schema names alone cannot supply absent marts or metrics.

Local sample validation uses the existing CSV-derived fixture. Preview publication views follow the exported Use Cases fields; unavailable ancillary fixture fields are NULL and the local publication ID is `local-preview`. Sample charts, totals and performance do not certify the Databricks pipeline, campaign mapping approvals, financial definitions or real warehouse performance.
