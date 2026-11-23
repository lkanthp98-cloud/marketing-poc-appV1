import { useState } from 'react';
import { Columns3, Database, Search } from 'lucide-react';
import { useResource } from './api';

type SchemaTable = { catalog: string; schema: string; name: string; columns: { name: string; type: string }[] };
const key = (table: SchemaTable) => `${table.catalog}.${table.schema}.${table.name}`;

export function SchemaBrowser({ revision }: { revision: number }) {
  const response = useResource<{ verification: string; tables: SchemaTable[] }>('/api/workspace-schema', revision);
  const [search, setSearch] = useState('');
  const [scope, setScope] = useState('');
  const [selected, setSelected] = useState('');
  const inventory = response.data?.tables ?? [];
  const scopes = [...new Set(inventory.map(table => `${table.catalog}.${table.schema}`))].sort();
  const tables = inventory.filter(table => (!scope || `${table.catalog}.${table.schema}` === scope) &&
    (key(table).toLowerCase().includes(search.toLowerCase()) || table.columns.some(column => column.name.toLowerCase().includes(search.toLowerCase()))));
  const info = tables.find(table => key(table) === selected) ?? tables[0];
  return <>
    <div className="population-note"><Database size={15} /><span>{response.data?.verification === 'LIVE_AUTHORIZED_INFORMATION_SCHEMA' ? 'Live column metadata for the selected app schema, visible to your Databricks identity.' : 'Schema reference from the uploaded explorer CSVs. This reference does not contain live records.'} Report filters do not affect schema metadata.</span></div>
    {response.error && <div className="inline-error">{response.error}</div>}
    <div className="schema-browser-controls"><label className="search-field"><Search size={16} /><input aria-label="Search tables or columns" placeholder="Search tables or columns…" value={search} onChange={event => setSearch(event.target.value)} /></label>
      <select aria-label="Schema location" value={scope} onChange={event => setScope(event.target.value)}><option value="">All catalog / schema locations</option>{scopes.map(name => <option key={name}>{name}</option>)}</select><span>{tables.length} tables</span></div>
    <div className="explorer-layout"><aside className="catalog-panel"><div className="catalog-title"><Database size={16} /><strong>Schema explorer</strong></div><div className="catalog-list">
      {tables.map(table => <button key={key(table)} className={`catalog-item ${info && key(table) === key(info) ? 'selected' : ''}`} onClick={() => setSelected(key(table))}><Columns3 size={15} /><span><strong>{table.name}</strong><small>{table.catalog}.{table.schema} · {table.columns.length} columns</small></span></button>)}
      {!tables.length && <p className="catalog-empty">{response.loading ? 'Loading schema metadata…' : 'No matching tables or columns.'}</p>}
    </div></aside><section className="metadata-panel">{info && <><span className="eyebrow">{info.catalog} / {info.schema}</span><h3 className="schema-table-name">{info.name}</h3><p className="metadata-description">{info.columns.length} associated columns · {key(info)}</p>
      <table className="schema-table"><thead><tr><th>Column name</th><th>Data type</th></tr></thead><tbody>{info.columns.map(column => <tr key={column.name}><td><Columns3 size={13} />{column.name}</td><td><code>{column.type || 'Unspecified'}</code></td></tr>)}</tbody></table></>}</section></div>
  </>;
}
