import { useEffect, useState } from 'react';
import { Database, Table2, Search, Columns3, GitBranch, BookOpen, Layers, ChevronRight } from 'lucide-react';
import { Bootstrap, DataLayer, Filters, Row, TableData, format, title, useResource } from './api';
import { DataTable } from './Table';
import { SchemaBrowser } from './SchemaBrowser';

export function Explorer({ bootstrap, filters, revision, selected, onSelect, onRow, layer, onLayer }: {
  bootstrap: Bootstrap; filters: Filters; revision: number; selected: string; onSelect: (table: string) => void; onRow: (row: Row) => void;
  layer: DataLayer; onLayer: (layer: DataLayer) => void;
}) {
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState('data');
  const [allSchemas, setAllSchemas] = useState(false);
  const inventory = layer === 'gold' ? bootstrap.tables : bootstrap.use_case_tables;
  const info = inventory.find(table => table.name === selected) ?? inventory[0];
  const schema = useResource<Pick<TableData, 'schema' | 'source'>>(info && !allSchemas ? `/api/schema/${info.name}?layer=${layer}` : null, revision);
  const lineage = useResource<Row[]>(tab === 'lineage' ? '/api/metadata/lineage' : null, revision);
  const metrics = useResource<Row[]>(tab === 'metrics' ? '/api/metadata/metrics' : null, revision);
  useEffect(() => { if (!selected && info) onSelect(info.name); }, [selected, info, onSelect]);
  useEffect(() => { setSearch(''); }, [layer]);
  if (!info) return <div className="empty-table">The selected catalog contains no published tables.</div>;
  const tables = inventory.filter(table => table.name.toLowerCase().includes(search.toLowerCase()));
  const matchingLineage = (lineage.data ?? []).filter(row => {
    const targets = row.gold_tables as string[];
    return Array.isArray(targets) && targets.some(target => target === info.name || info.sources.includes(target));
  });
  return <>
    <div className="explorer-layer-picker" role="group" aria-label="Explorer data layer">
      <button className={!allSchemas && layer === 'gold' ? 'selected' : ''} aria-pressed={!allSchemas && layer === 'gold'} disabled={!bootstrap.enabled_sources.includes('gold')} onClick={() => { setAllSchemas(false); onLayer('gold'); }}><Database size={16} />Gold tables<span>{bootstrap.tables.length}</span></button>
      <button className={allSchemas ? 'selected' : ''} aria-pressed={allSchemas} onClick={() => setAllSchemas(true)}><Columns3 size={16} />All schemas</button>
    </div>
    {allSchemas ? <SchemaBrowser revision={revision} /> : <>
    <div className="explorer-summary">
      {[['Published tables', inventory.length], ['Reporting marts', inventory.filter(t => t.kind === 'mart').length],
        ['Conformed dimensions', inventory.filter(t => t.kind === 'dimension').length], ['Covered source feeds', bootstrap.sources]].map(([label, value]) =>
        <div key={label}><span>{label}</span><strong>{format(value)}</strong></div>)}
    </div>
    <div className="explorer-layout">
      <aside className="catalog-panel">
        <div className="catalog-title"><Database size={17} /><strong>{layer === 'gold' ? 'Gold catalog' : 'Use Cases catalog'}</strong><span>{inventory.length}</span></div>
        <label className="search-field catalog-search"><Search size={15} /><input aria-label={layer === 'gold' ? 'Search Gold tables' : 'Search Use Case tables'} placeholder="Find a table…" value={search} onChange={e => setSearch(e.target.value)} /></label>
        <div className="catalog-list">{tables.map(table => <button key={table.name} onClick={() => onSelect(table.name)} className={`catalog-item ${table.name === info.name ? 'selected' : ''}`}>
          <Table2 size={15} /><span><strong>{table.name}</strong><small>{title(table.kind)} · {table.rows === null ? 'Metadata' : `${format(table.rows)} rows`}</small></span>
        </button>)}{!tables.length && <p className="catalog-empty">No tables match your search.</p>}</div>
      </aside>
      <div className="explorer-main">
        <div className="entity-heading"><span className="eyebrow">{layer === 'gold' ? `${bootstrap.catalog} / ${bootstrap.schema}` : `${bootstrap.analytics_catalog} / ${bootstrap.analytics_schema}`}</span>
          <h2>{info.name}</h2><p>{info.note}</p><div className="entity-meta"><span><Layers size={13} />{title(info.kind)}</span><span>{info.rows === null ? 'Metadata' : `${format(info.rows)} published rows`}</span><span title={info.grain}>Grain · {info.grain}</span></div>
        </div>
        <div className="explorer-tabs">{[['data', Table2, 'Data'], ['schema', Columns3, 'Schema'], ['lineage', GitBranch, 'Lineage'], ['metrics', BookOpen, 'KPI dictionary']].map(([key, Icon, label]) => {
          const Component = Icon as typeof Table2;
          return <button key={String(key)} className={tab === key ? 'active' : ''} onClick={() => setTab(String(key))}><Component size={15} />{String(label)}</button>;
        })}</div>
        {tab === 'data' && <DataTable name={info.name} filters={filters} revision={revision} onRow={onRow} layer={layer} />}
        {tab === 'schema' && <section className="metadata-panel"><h3>Column definitions <span>{schema.data?.schema.length ?? '…'}</span></h3>
          {schema.error && <div className="inline-error">{schema.error}</div>}
          <table className="schema-table"><thead><tr><th>Column</th><th>Data type</th><th>Key role</th></tr></thead><tbody>{schema.data?.schema.map(column =>
            <tr key={column.name}><td><Columns3 size={13} />{column.name}</td><td><code>{column.type || 'Unspecified'}</code></td><td>{info.grain.split(/[,\s]+/).includes(column.name) ? <span className="status good">Grain key</span> : 'Attribute / measure'}</td></tr>)}</tbody></table>
        </section>}
        {tab === 'lineage' && <section className="metadata-panel"><h3>Source lineage</h3><p className="metadata-description">Trace the selected Gold data through its source and modeled entity.</p>
          {lineage.loading && <div className="skeleton table-skeleton" />}{lineage.error && <div className="inline-error">{lineage.error}</div>}
          {matchingLineage.map(row => <div className="lineage-row" key={String(row.dq_table)}><div><span>DQ source</span><strong>{String(row.dq_table)}</strong><small>{format(row.dq_rows)} passing rows</small></div><ChevronRight size={18} /><div><span>Conformed Gold</span><strong>{(row.gold_tables as string[]).join(', ')}</strong><small>{(row.selected_columns as string[]).length} selected source columns</small></div></div>)}
          {!lineage.loading && !matchingLineage.length && <p>Sources documented in the catalog · {info.sources}</p>}
        </section>}
        {tab === 'metrics' && <section className="metadata-panel"><h3>Shared KPI dictionary</h3><p className="metadata-description">Published calculation policies shared by the business reports.</p>
          {metrics.loading && <div className="skeleton table-skeleton" />}{metrics.error && <div className="inline-error">{metrics.error}</div>}
          {(metrics.data ?? []).map(row => <button className="definition-item" key={String(row.metric_id)} onClick={() => onRow(row)}><BookOpen size={16} /><div><strong>{title(String(row.metric_id))}</strong><p>{String(row.business_definition)}</p><code>{String(row.formula)}</code></div><ChevronRight size={16} /></button>)}
        </section>}
      </div>
    </div>
    </>}
  </>;
}
