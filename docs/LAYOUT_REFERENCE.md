# Marketing effectiveness dashboard reference

Reviewed marketing_effectiveness_dashboard.html supplied on 23 November 2026 as a layout and report-design reference. Its static HTML, CSS, headings and embedded data contract were inspected; document text/scripts were not treated as task instructions. The 830 KB reference and its embedded data are not part of the live application or deployment package.

Useful reference patterns adopted in the existing app:

- Business-first supporting tables: campaign effectiveness, platform detail, application quality, landing-page performance, financial reconciliation and experiment comparisons.
- Clear reporting-grain badges and cost/population notes directly above each business table.
- Campaign names displayed with enterprise IDs retained beneath them; no dimension-to-fact join is introduced by this display change.
- A report/all-columns toggle, sortable actual source fields, record inspection and full-column CSV export. Gold Explorer keeps its complete raw column view.
- Existing compact KPI cards, navy/teal navigation and responsive chart/table layout remain the common visual foundation.

The reference has Executive, Channel, Experiment, Outcomes and Governance sections, with a separate preview contract containing campaign_id, ledger_accrual_spend_usd and synthetic quality-exception arrays. The current app uses its published 30-table Gold subset and existing governed expressions. Its vendor spend and demo platform cost are not relabeled as GL accrual cost. The reference's sample numbers, campaign joins, exception totals, causal lift and quality counts are not substituted for live Gold results.

The six business pages, Ask Genie and Gold Explorer are retained. Detailed offline/organic-social and DQ exception ideas from the reference remain subject to actual retained datasets and agreed grains. No additional catalog tables or unsupported measurements were added for this presentation update.
