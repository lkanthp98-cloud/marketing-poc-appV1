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

The historical Use Cases export remains in the normalized reference for traceability, but it is not a runtime data source. All 42 dashboard elements (24 metrics and 18 charts) query the corresponding Gold mart directly. `dashboard-data-mapping.csv` identifies each input and its required columns in the original source Gold. The active sample schema browser exposes Bronze, Silver, Model and Gold: 377 tables and 4,817 columns. Live schema browsing uses authorized information_schema results for the selected app schema only. The dedicated app_gold publication has exactly 30 objects; see [subset publication](APP_GOLD_SUBSET.md).

The Gold marts retain their existing business grains, currency and metric definitions. No additional physical use-case tables are created. Campaign labels resolve from the Gold campaign master without joining that dimension onto aggregate facts; this prevents duplicate dimension rows multiplying measures. Missing/conflicting names are explicit. Unsupported campaign/platform filters make a visual unavailable; the app does not fabricate missing attribution.

The read-only Gold audit notebook checks master uniqueness, missing names, missing dimension references, conflicting mart labels and duplicate declared grain rows. Run it in the actual workspace: exported schemas alone cannot prove live row correctness.

The sample fixture independently reproduces supported aggregates from the supplied synthetic CSVs. Some ancillary fields are simplified. Tests validate numeric baselines, exact filtering, labels, routing and unavailable states locally; they do not certify Spark execution or live financial reconciliation.
