import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, Search, ArrowDownWideNarrow } from 'lucide-react';
import { DataLayer, Filters, Row, TableData, format, query, title, useResource } from './api';

export function CellValue({ name, value, row }: { name: string; value: unknown; row: Row }) {
  if (value === null || value === undefined) return <span className="null-value">—</span>;
  if (typeof value === 'boolean') return <span className={`status ${value ? 'good' : 'neutral'}`}>{value ? 'Yes' : 'No'}</span>;
  if (typeof value === 'number') {
    if (/absolute_lift|difference_ci_lower|difference_ci_upper/.test(name)) return <span className="numeric">{(value * 100).toFixed(2)} pp</span>;
    if (/p_value/.test(name)) return <span className="numeric">{value.toFixed(4)}</span>;
    if (/_pct$/.test(name)) return <span className="numeric">{value.toFixed(1)}%</span>;
    const percent = /rate|share|utilization|attainment|relative_lift|confidence_level/.test(name) && !/amount|denominator|numerator/.test(name);
    const currency = /_usd$/.test(name) ? 'usd' : /spend_amount|invoice_amount|budget_amount|tax_amount|spend$/.test(name) ? 'currency' : 'number';
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

export function DataTable({ name, filters, revision, onRow, compact = false, layer = 'gold' }: {
  name: string; filters: Filters; revision: number; onRow: (row: Row) => void; compact?: boolean; layer?: DataLayer;
}) {
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sort, setSort] = useState('');
  const [descending, setDescending] = useState(true);
  useEffect(() => { const timeout = setTimeout(() => setDebouncedSearch(search), 250); return () => clearTimeout(timeout); }, [search]);
  const filterString = query(filters);
  useEffect(() => { setPage(0); setSort(''); setSearch(''); }, [name, layer]);
  useEffect(() => setPage(0), [filterString, debouncedSearch, size]);
  const params = `${filterString}&layer=${layer}&page=${page}&size=${size}&sort=${encodeURIComponent(sort)}&descending=${descending}&search=${encodeURIComponent(debouncedSearch)}`;
  const { data, loading, error } = useResource<TableData>(`/api/table/${encodeURIComponent(name)}?${params}`, revision);
  const visible = data?.schema ?? [];
  return <section className={`data-table-panel ${compact ? 'compact-table' : ''}`}>
    <div className="table-toolbar">
      <div><h3>{compact ? 'Supporting records' : 'Data preview'}</h3><span className="table-source">{data?.source ?? name}</span></div>
      <div className="table-tools">
        <label className="search-field"><Search size={15} /><input aria-label="Search table records" placeholder="Search records…" value={search} onChange={e => setSearch(e.target.value)} /></label>
        <a className="button secondary small" href={`/api/export/${encodeURIComponent(name)}?${filterString}&layer=${layer}&search=${encodeURIComponent(debouncedSearch)}`} title="Export up to 10,000 filtered rows"><Download size={14} />Export CSV</a>
      </div>
    </div>
    {error ? <div className="inline-error">{error}</div> : <div className={`table-scroll ${loading ? 'loading-table' : ''}`} aria-busy={loading}>
      {!data && loading ? <div className="table-skeleton skeleton" /> : <table>
        <thead><tr>{visible.map(column => <th key={column.name}><button onClick={() => {
          setPage(0); setSort(column.name); setDescending(sort === column.name ? !descending : true);
        }}>{title(column.name)}{sort === column.name && <ArrowDownWideNarrow size={12} />}</button></th>)}</tr></thead>
        <tbody>{data?.rows.map((row, index) => <tr key={index} tabIndex={0} onClick={() => onRow(row)} onKeyDown={e => { if (e.key === 'Enter') onRow(row); }}>
          {visible.map(column => <td key={column.name}><CellValue name={column.name} value={row[column.name]} row={row} /></td>)}
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
