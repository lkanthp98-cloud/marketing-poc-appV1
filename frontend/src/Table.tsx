import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, Search, ArrowDownWideNarrow } from 'lucide-react';
import { DataLayer, Filters, Row, TableData, format, query, title, useResource } from './api';

const REPORTS: Record<string, { title: string; grain: string; note: string; columns: string[]; labels?: Record<string,string> }> = {
  mart_demo_campaign_economics: { title: 'Campaign effectiveness', grain: 'Campaign / platform cohort',
    note: 'Synthetic campaign cohorts. Cost uses platform delivery in USD; contribution follows each row\'s observation horizon.',
    columns: ['campaign_key','platform','campaign_resolution_status','platform_spend_usd','crm_leads','qualified_leads','applications','approved_applications','funded_accounts','cost_per_funded_account_usd','observed_contribution_usd','contribution_months','source_campaign_id','pack_version'],
    labels: {campaign_key:'Campaign',platform_spend_usd:'Platform spend (USD)',crm_leads:'CRM leads',cost_per_funded_account_usd:'Cost / funded account (USD)',observed_contribution_usd:'Observed contribution (USD)',contribution_months:'Observation months'} },
  mart_platform_conversion_efficiency: { title: 'Platform performance detail', grain: 'Native platform reporting',
    note: 'Native conversion definitions and source currency are retained.',
    columns: ['platform','report_date','source_campaign_name','resolved_campaign_key','source_campaign_id','currency','spend_amount','reported_impressions','reported_clicks','reported_click_rate','reported_conversions','platform_reported_cpa','campaign_resolution_status'],labels:{resolved_campaign_key:'Campaign',spend_amount:'Platform spend'} },
  mart_application_quality_monthly: { title: 'Application quality', grain: 'Month / product / market / campaign',
    note: 'Operational banking application outcomes; current approval and rejection status.',
    columns: ['application_month','resolved_campaign_key','product_id','market_cd','segment_id','applications','approved_applications','declined_applications','approval_rate','rejection_rate','campaign_resolution_status'],labels:{resolved_campaign_key:'Campaign'} },
  mart_website_engagement_daily: { title: 'Website and landing-page performance', grain: 'Session date / landing page / device',
    note: 'Website engagement and application-submit sessions at their published grain.',
    columns: ['session_date','landing_page_path','device_category','resolved_campaign_key','sessions','engaged_sessions','sessions_with_application_submit','campaign_resolution_status'],labels:{resolved_campaign_key:'Campaign'} },
  mart_vendor_invoice_platform_comparison: { title: 'Invoice and platform reconciliation', grain: 'Source campaign / billing period / currency',
    note: 'Invoice and platform costs are separate representations; their difference is not an additional expense.',
    columns: ['mapping_source_system','campaign_match_token','invoice_period_start','invoice_period_end','currency','reported_invoice_amount','reported_tax_amount','platform_spend_amount','reported_invoice_minus_platform','comparison_status'] },
  mart_demo_experiment_comparison: { title: 'Experiment comparison detail', grain: 'Experiment / treatment / control',
    note: 'Observed lift and nominal uncertainty. Review the interval and configured primary outcome.',
    columns: ['experiment_id','variant_id','control_variant','absolute_lift','relative_lift','difference_ci_lower','difference_ci_upper','nominal_two_sided_p_value','nominal_significant','comparison_status'] },
};

export function CellValue({ name, value, row }: { name: string; value: unknown; row: Row }) {
  if (value === null || value === undefined) return <span className="null-value">—</span>;
  if (typeof value === 'boolean') return <span className={`status ${value ? 'good' : 'neutral'}`}>{value ? 'Yes' : 'No'}</span>;
  if (typeof value === 'number') {
    if (/absolute_lift|difference_ci_lower|difference_ci_upper/.test(name)) return <span className="numeric">{(value * 100).toFixed(2)} pp</span>;
    if (/p_value/.test(name)) return <span className="numeric">{value.toFixed(4)}</span>;
    if (/_pct$/.test(name)) return <span className="numeric">{value.toFixed(1)}%</span>;
    const percent = /rate|share|utilization|attainment|relative_lift|confidence_level/.test(name) && !/amount|denominator|numerator/.test(name);
    const currency = /_usd$/.test(name) ? 'usd' : /spend_amount|invoice_amount|budget_amount|tax_amount|invoice_minus_platform|reported_cpa|spend$/.test(name) ? 'currency' : 'number';
    return <span className="numeric">{format(value, percent ? 'percent' : currency, String(row.currency || 'USD'))}</span>;
  }
  const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
  if (/status|resolution|validation/.test(name)) {
    const good = /^(matched|resolved|verified_by_crosswalk|observed_return_available|approved|pass)$/i.test(text);
    const warning = /review|missing|unavailable|unmapped|unresolved|unapproved|demo_only|conflict|incomplete/.test(text);
    return <span className={`status ${good ? 'good' : warning ? 'warning' : 'neutral'}`}>{title(text)}</span>;
  }
  return <span className="cell-text" title={text}>{/^\d{4}-\d{2}-\d{2}$/.test(text) ? text : text}</span>;
}

export function DataTable({ name, filters, revision, onRow, compact = false, layer = 'gold', campaignNames = {} }: {
  name: string; filters: Filters; revision: number; onRow: (row: Row) => void; compact?: boolean; layer?: DataLayer; campaignNames?: Record<string,string>;
}) {
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sort, setSort] = useState('');
  const [descending, setDescending] = useState(true);
  const [allColumns, setAllColumns] = useState(false);
  useEffect(() => { const timeout = setTimeout(() => setDebouncedSearch(search), 250); return () => clearTimeout(timeout); }, [search]);
  const filterString = query(filters);
  useEffect(() => { setPage(0); setSort(''); setSearch(''); setAllColumns(false); }, [name, layer]);
  useEffect(() => setPage(0), [filterString, debouncedSearch, size]);
  const params = `${filterString}&layer=${layer}&page=${page}&size=${size}&sort=${encodeURIComponent(sort)}&descending=${descending}&search=${encodeURIComponent(debouncedSearch)}`;
  const { data, loading, error } = useResource<TableData>(`/api/table/${encodeURIComponent(name)}?${params}`, revision);
  const report = compact ? REPORTS[name] : undefined;
  const schema = data?.schema ?? [];
  const visible = report && !allColumns ? report.columns.flatMap(field => schema.filter(column => column.name === field)) : schema;
  return <section className={`data-table-panel ${compact ? 'compact-table' : ''}`}>
    <div className="table-toolbar">
      <div><h3>{report?.title ?? (compact ? 'Supporting records' : 'Data preview')}</h3><span className="table-source">{data?.source ?? name}</span></div>
      <div className="table-tools">
        {report && <button className="button secondary small" aria-pressed={allColumns} onClick={() => setAllColumns(value => !value)}>{allColumns ? 'Report columns' : 'All columns'}</button>}
        <label className="search-field"><Search size={15} /><input aria-label="Search table records" placeholder="Search records…" value={search} onChange={e => setSearch(e.target.value)} /></label>
        <a className="button secondary small" href={`/api/export/${encodeURIComponent(name)}?${filterString}&layer=${layer}&search=${encodeURIComponent(debouncedSearch)}`} title="Export up to 10,000 filtered rows"><Download size={14} />Export CSV</a>
      </div>
    </div>
    {report && <div className="report-context"><span className="report-grain">{report.grain}</span><span>{report.note}</span></div>}
    {error ? <div className="inline-error">{error}</div> : <div className={`table-scroll ${loading ? 'loading-table' : ''}`} aria-busy={loading}>
      {!data && loading ? <div className="table-skeleton skeleton" /> : <table>
        <thead><tr>{visible.map(column => <th key={column.name}><button onClick={() => {
          setPage(0); setSort(column.name); setDescending(sort === column.name ? !descending : true);
        }}>{report?.labels?.[column.name] ?? title(column.name)}{sort === column.name && <ArrowDownWideNarrow size={12} />}</button></th>)}</tr></thead>
        <tbody>{data?.rows.map((row, index) => <tr key={index} tabIndex={0} onClick={() => onRow(row)} onKeyDown={e => { if (e.key === 'Enter') onRow(row); }}>
          {visible.map(column => <td key={column.name}>{compact && /^(resolved_)?campaign_key$/.test(column.name) && campaignNames[String(row[column.name])] ? <span className="campaign-cell"><strong>{campaignNames[String(row[column.name])]}</strong><small>{String(row[column.name])}</small></span> : <CellValue name={column.name} value={row[column.name]} row={row} />}</td>)}
        </tr>)}</tbody>
      </table>}
      {data && !data.rows.length && <div className="empty-table">No records match the selected filters.</div>}
    </div>}
    <div className="table-footer"><span>{data && data.total > 0 ? `${page * size + 1}–${Math.min((page + 1) * size, data.total)} of ${format(data.total)} records` : loading ? 'Loading records…' : '0 records'}</span>
      <div className="pagination"><label>Rows <select aria-label="Rows per page" value={size} onChange={e => setSize(Number(e.target.value))}><option>20</option><option>50</option><option>100</option></select></label>
        <button className="icon-button" aria-label="Previous page" disabled={page === 0 || loading} onClick={() => setPage(page - 1)}><ChevronLeft size={16} /></button>
        <span>Page {page + 1}</span>
        <button className="icon-button" aria-label="Next page" disabled={loading || !data || (page + 1) * size >= data.total} onClick={() => setPage(page + 1)}><ChevronRight size={16} /></button>
      </div>
    </div>
  </section>;
}
