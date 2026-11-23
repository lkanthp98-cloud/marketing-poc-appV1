import { useCallback, useEffect, useState } from 'react';
import {
  Activity, BarChart3, Bookmark, CalendarDays, Check, ChevronDown, CircleHelp, Database,
  Download, FlaskConical, Info, Landmark, LayoutDashboard, Menu, RadioTower, RefreshCw,
  SlidersHorizontal, TrendingDown, TrendingUp, UsersRound, X, Layers, ExternalLink,
} from 'lucide-react';
import { Bootstrap, ChartData, Dashboard, DataLayer, Filters, Metric, Row, format, query, title, useResource } from './api';
import { Chart } from './Chart';
import { DataTable, CellValue } from './Table';
import { Explorer } from './Explorer';
import { ConnectionDialog } from './Connection';
import { Genie } from './Genie';

const navigation = [
  { id: 'overview', label: 'Executive Overview', icon: LayoutDashboard },
  { id: 'campaigns', label: 'Campaign & Paid Media', icon: BarChart3 },
  { id: 'acquisition', label: 'Customer Acquisition', icon: UsersRound },
  { id: 'digital', label: 'Digital & Offline', icon: RadioTower },
  { id: 'finance', label: 'Financial Performance', icon: Landmark },
  { id: 'experiments', label: 'Experiments & Brand', icon: FlaskConical },
  { id: 'genie', label: 'Ask Genie', icon: CircleHelp },
  { id: 'explorer', label: 'Gold Data Explorer', icon: Database },
];

function LoadingPage() {
  return <div className="page-loading" aria-label="Loading dashboard"><div className="kpi-grid">{[1, 2, 3, 4].map(i => <div className="skeleton kpi-skeleton" key={i} />)}</div><div className="charts-grid"><div className="skeleton chart-skeleton" /><div className="skeleton chart-skeleton" /></div></div>;
}

function MetricCard({ metric, currency, comparing, onClick }: { metric: Metric; currency: string; comparing: boolean; onClick: () => void }) {
  const positive = metric.change !== null && metric.change >= 0;
  const favorable = metric.direction === 'up' ? positive : !positive;
  const changeClass = metric.direction === 'neutral' ? 'neutral' : favorable ? 'favorable' : 'unfavorable';
  return <button className="metric-card" onClick={onClick} aria-label={`Details for ${metric.label}`}>
    <div className="metric-label">{metric.label}<Info size={14} /></div>
    <strong className="metric-value">{format(metric.value, metric.format, currency, true)}</strong>
    <div className="metric-footer">{comparing && metric.change !== null ? <><span className={`metric-change ${changeClass}`}>{positive ? <TrendingUp size={13} /> : <TrendingDown size={13} />}{format(Math.abs(metric.change), 'percent')}</span><span>vs previous period</span></> : <span>{metric.unavailable_reason ? 'Unavailable for this selection' : metric.value === null ? 'No eligible observations' : metric.format === 'usd' ? 'Observed source values · USD' : comparing ? 'Previous period unavailable' : 'Selected reporting scope'}</span>}</div>
  </button>;
}

function SelectFilter({ label, value, options, onChange }: { label: string; value: string; options: { value: string; label: string }[]; onChange: (value: string) => void }) {
  return <label className="select-filter"><span>{label}</span><div><select aria-label={label} value={value} onChange={e => onChange(e.target.value)}>{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select><ChevronDown size={13} /></div></label>;
}

function Workspace({ bootstrap }: { bootstrap: Bootstrap }) {
  const defaults: Filters = { start: bootstrap.dates.start, end: bootstrap.dates.end, campaign: '', platform: '', product: '', market: '', currency: 'USD', plan: bootstrap.plans.at(-1) ?? '', compare: false };
  const [filters, setFilters] = useState<Filters>(defaults);
  const [page, setPage] = useState('overview');
  const [revision, setRevision] = useState(0);
  const [advanced, setAdvanced] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [drawer, setDrawer] = useState<{ title: string; description?: string; table?: string; row?: Row } | null>(null);
  const [expanded, setExpanded] = useState<ChartData | null>(null);
  const [explorerTable, setExplorerTable] = useState('mart_vendor_media_daily');
  const [explorerLayer, setExplorerLayer] = useState<DataLayer>('gold');
  const [help, setHelp] = useState(false);
  const [connectionOpen, setConnectionOpen] = useState(false);
  const { data, loading, error } = useResource<Dashboard>(!['explorer', 'genie'].includes(page) ? `/api/dashboard/${page}?${query(filters)}` : null, revision);
  const readiness = useResource<Row[]>(help ? '/api/metadata/readiness' : null);
  const platformFilter = useCallback((value: string) => setFilters(previous => ({ ...previous, platform: value })), []);
  const explore = useCallback((table: string) => { setExplorerTable(table); setExplorerLayer('gold'); setPage('explorer'); setDrawer(null); }, []);
  const showRow = useCallback((row: Row) => setDrawer({ title: 'Record details', row }), []);
  const selectExplorer = useCallback((table: string) => setExplorerTable(table), []);
  const selectLayer = useCallback((layer: DataLayer) => { setExplorerLayer(layer); setExplorerTable(''); }, []);
  const activeLayer = page === 'explorer' ? explorerLayer : bootstrap.analytics_layer;
  const sourceLocation = activeLayer === 'gold' ? `${bootstrap.catalog}.${bootstrap.schema}` : `${bootstrap.analytics_catalog}.${bootstrap.analytics_schema}`;
  const current = navigation.find(item => item.id === page)!;
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 3000); return () => clearTimeout(timer); }, [toast]);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => { if (event.key === 'Escape') { setDrawer(null); setExpanded(null); setHelp(false); setSidebarOpen(false); } };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);
  useEffect(() => {
    if (!drawer && !expanded && !help) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    const focusable = () => [...(dialog?.querySelectorAll<HTMLElement>('button, a[href], input, select, [tabindex="0"]') ?? [])].filter(element => !element.hasAttribute('disabled'));
    focusable()[0]?.focus();
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const elements = focusable(), first = elements[0], last = elements.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    dialog?.addEventListener('keydown', trapFocus);
    return () => { dialog?.removeEventListener('keydown', trapFocus); if (previous?.isConnected) previous.focus(); };
  }, [drawer, expanded, help]);
  function change<K extends keyof Filters>(key: K, value: Filters[K]) { setFilters(previous => ({ ...previous, [key]: value })); }
  const allOption = (label: string, values: string[]) => [{ value: '', label }, ...values.map(value => ({ value, label: title(value) }))];
  const scopeLimitations = data && page !== 'explorer' ? [...new Set([...data.metrics.flatMap(m => m.unsupported_filters), ...data.charts.flatMap(c => c.unsupported_filters)])] : [];
  return <div className="app-shell">
    {sidebarOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
    <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
      <div className="brand"><div className="brand-mark"><BarChart3 size={22} strokeWidth={2.1} /></div><div><strong>Marketing<span>Intelligence</span></strong></div></div>
      <div className="sidebar-section-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{navigation.map(item => <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} onClick={() => { setPage(item.id); setSidebarOpen(false); }}><item.icon size={18} /><span>{item.label}</span>{page === item.id && <span className="active-marker" />}</button>)}</nav>
      <div className="sidebar-bottom"><div className="foundation"><Layers size={18} /><div><strong>Connected data foundation</strong><span>{bootstrap.sources === null ? 'Published datasets' : `${bootstrap.sources} source feeds`} · Unity Catalog</span></div></div>
        <button className="sidebar-help" onClick={() => setHelp(true)}><CircleHelp size={17} />Definitions & availability</button>
        <div className="workspace-identity"><div className="avatar">{bootstrap.mode === 'preview' ? 'PV' : bootstrap.viewer.slice(0, 2).toUpperCase()}</div><div><strong>{bootstrap.mode === 'preview' ? 'POC workspace' : bootstrap.viewer}</strong><span>{bootstrap.mode === 'preview' ? 'Source-derived local preview' : bootstrap.shared_data ? 'Shared app identity' : 'Databricks user authorization'}</span></div></div>
      </div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="breadcrumbs"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button><span>Marketing Analytics</span><span className="breadcrumb-slash">/</span><strong>{current.label}</strong></div>
        <div className="topbar-right"><span className={`connection-pill ${bootstrap.mode === 'preview' ? 'preview' : ''}`}><span className="connection-dot" />{bootstrap.mode === 'preview' ? 'Local data preview' : 'Databricks Gold'}</span><button className="icon-button" aria-label="Connection settings" onClick={() => setConnectionOpen(true)}><SlidersHorizontal size={18} /></button><button className="icon-button" aria-label="Metric help and availability" onClick={() => setHelp(true)}><CircleHelp size={18} /></button><div className="avatar top-avatar">{bootstrap.mode === 'preview' ? 'PV' : bootstrap.viewer.slice(0, 2).toUpperCase()}</div></div>
      </header>
      <main className={page === 'genie' ? 'genie-page' : undefined}>
        <div className="page-heading"><div><span className="eyebrow">{page === 'explorer' ? 'YOUR ANALYTICS FOUNDATION' : data?.eyebrow ?? 'MARKETING INTELLIGENCE'}</span><h1>{current.label === 'Executive Overview' ? 'Executive overview' : current.label}</h1><p>{page === 'explorer' ? 'Discover, inspect and trace the data behind every metric.' : data?.subtitle ?? 'Explore your connected marketing performance.'}</p></div>
          <div className="page-heading-actions"><button className="button secondary" onClick={() => { const saved = localStorage.getItem('marketing-saved-filters'); if (saved) { try { setFilters({ ...defaults, ...JSON.parse(saved) }); setToast('Saved filters restored.'); } catch { setToast('Saved filters could not be restored.'); } } else { setToast('Use Save view to store the current filters.'); } }} title="Restore your saved filter selection"><Bookmark size={15} />Saved view</button><button className="button primary" onClick={() => setRevision(value => value + 1)} disabled={loading && page !== 'explorer'}><RefreshCw size={15} className={loading && page !== 'explorer' ? 'spinning' : ''} />Refresh data</button></div>
        </div>
        <section className="filter-panel" aria-label="Report filters"><div className="filter-main"><label className="date-filter"><CalendarDays size={16} /><input type="date" aria-label="Start date" value={filters.start} max={filters.end || undefined} onChange={e => change('start', e.target.value)} /><span>to</span><input type="date" aria-label="End date" value={filters.end} min={filters.start || undefined} onChange={e => change('end', e.target.value)} /></label>
          <SelectFilter label="Campaign" value={filters.campaign} options={[{ value: '', label: 'All campaigns' }, ...bootstrap.campaigns.map(c => ({ value: c.campaign_key, label: c.campaign_name }))]} onChange={value => change('campaign', value)} />
          <SelectFilter label="Platform" value={filters.platform} options={allOption('All platforms', bootstrap.platforms)} onChange={value => change('platform', value)} />
          <button className={`button filter-toggle ${advanced ? 'selected' : ''}`} onClick={() => setAdvanced(!advanced)} aria-expanded={advanced}><SlidersHorizontal size={15} />More filters{(filters.product || filters.market) && <span className="filter-count">{Number(Boolean(filters.product)) + Number(Boolean(filters.market))}</span>}</button>
          <button className="text-button reset-filters" onClick={() => setFilters(defaults)}>Reset</button>
        </div>
          {advanced && <div className="filter-advanced"><SelectFilter label="Product" value={filters.product} options={allOption('All products', bootstrap.products)} onChange={value => change('product', value)} /><SelectFilter label="Market" value={filters.market} options={allOption('All markets', bootstrap.markets)} onChange={value => change('market', value)} /><SelectFilter label="Currency" value={filters.currency} options={bootstrap.currencies.map(value => ({ value, label: value }))} onChange={value => change('currency', value)} /><SelectFilter label="Plan version" value={filters.plan} options={bootstrap.plans.map(value => ({ value, label: value }))} onChange={value => change('plan', value)} /><button className="button secondary small" onClick={() => { localStorage.setItem('marketing-saved-filters', JSON.stringify(filters)); setToast('Filters saved in this browser.'); }}><Bookmark size={14} />Save view</button></div>}
          <div className="filter-footer"><span><Database size={12} />{sourceLocation}<span className="filter-footer-divider">·</span>{bootstrap.mode === 'preview' ? 'Source-derived POC data' : 'Gold-backed use-case analytics'}</span><label className="compare-toggle"><input type="checkbox" checked={filters.compare} onChange={e => change('compare', e.target.checked)} />Compare previous period</label></div>
        </section>
        {page !== 'genie' && bootstrap.warnings.length > 0 && <details className="source-notices"><summary>{bootstrap.warnings.length} Gold data availability notices</summary><ul>{bootstrap.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></details>}
        <div hidden={page !== 'genie'}><Genie /></div>
        {page === 'genie' ? null : page === 'explorer' ? <Explorer bootstrap={bootstrap} filters={filters} revision={revision} selected={explorerTable} onSelect={selectExplorer} onRow={showRow} layer={explorerLayer} onLayer={selectLayer} /> : error ? <section className="error-card"><Activity size={26} /><h2>We couldn’t load this report</h2><p>{error}</p><button className="button primary" onClick={() => setRevision(value => value + 1)}>Retry request</button></section> : loading ? <LoadingPage /> : data && <>
          <div className="population-note"><Info size={14} /><span>{bootstrap.shared_data && <>Shared app dataset. </>}Vendor delivery, synthetic campaign cohorts and banking outcomes are separate reporting populations. Open a metric to inspect its scope.</span></div><div className="section-heading"><h2>Performance at a glance</h2><span>{filters.currency} where applicable<span className="separator">·</span>Ratio of totals</span></div>
          <div className="kpi-grid">{data.metrics.map(metric => <MetricCard key={metric.label} metric={metric} currency={filters.currency} comparing={filters.compare} onClick={() => setDrawer({ title: metric.label, description: metric.description, table: metric.table, row: { value: metric.value, previous_period: metric.previous, reporting_table: metric.source, unavailable_reason: metric.unavailable_reason, unsupported_filters: metric.unsupported_filters } })} />)}</div>
          {(scopeLimitations.length > 0 || data.metrics.some(m => m.unavailable_reason)) && (filters.campaign || filters.platform || filters.product || filters.market || filters.plan || page === 'experiments') && <div className="scope-note"><Info size={14} /><span>Unsupported campaign or platform selections make a metric unavailable. Inspect each metric for its scope; fixed experiment windows retain their configured period.</span></div>}
          <div className={`charts-grid page-${page}`}><Chart chart={data.charts[0]} currency={filters.currency} onExplore={explore} onPlatform={platformFilter} onExpand={setExpanded} /><Chart chart={data.charts[1]} currency={filters.currency} onExplore={explore} onPlatform={platformFilter} onExpand={setExpanded} /></div>
          <div className="lower-grid"><Chart chart={data.charts[2]} currency={filters.currency} onExplore={explore} onPlatform={platformFilter} onExpand={setExpanded} /><div className="insight-card"><div className="insight-icon"><Layers size={20} /></div><span className="eyebrow">UNDERSTAND THE NUMBERS</span><h3>{page === 'overview' ? 'From performance to provenance.' : 'Every metric has a defined scope.'}</h3><p>{page === 'overview' ? 'Follow each result to its Gold table, reporting grain and source coverage. Explore the evidence behind your marketing decisions.' : 'Review the published formula, native currency and source population before comparing outcomes across channels.'}</p><button className="button secondary" disabled={!data.table} onClick={() => explore(data.table)}><Database size={15} />Explore supporting data</button><div className="insight-meta"><Check size={13} />Published metric definitions</div></div></div>
          {data.table && <DataTable name={data.table} filters={filters} revision={revision} onRow={showRow} compact layer={bootstrap.analytics_layer} />}
        </>}
        <footer className="workspace-footer"><span>Marketing Intelligence</span><span>{bootstrap.mode === 'preview' ? 'Local CSV-derived preview · live workspace validation pending' : 'Databricks Gold · access follows your identity'}</span></footer>
      </main>
    </div>
    {toast && <div className="toast" role="status"><Check size={16} />{toast}</div>}
    {connectionOpen && <ConnectionDialog onClose={() => setConnectionOpen(false)} />}
    {drawer && <div className="overlay" onClick={() => setDrawer(null)}><aside className="drawer" role="dialog" aria-modal="true" aria-label={drawer.title} onClick={e => e.stopPropagation()}><div className="drawer-heading"><div><span className="eyebrow">SUPPORTING DETAILS</span><h2>{drawer.title}</h2></div><button className="icon-button" aria-label="Close details" onClick={() => setDrawer(null)}><X size={20} /></button></div>{drawer.description && <p className="drawer-description">{drawer.description}</p>}<dl>{Object.entries(drawer.row ?? {}).map(([key, value]) => <div key={key}><dt>{title(key)}</dt><dd><CellValue name={key} value={value} row={drawer.row ?? {}} /></dd></div>)}</dl>{drawer.table && <button className="button primary" onClick={() => explore(drawer.table!)}><Database size={15} />Explore supporting data</button>}</aside></div>}
    {expanded && <div className="overlay expanded-overlay" onClick={() => setExpanded(null)}><div className="expanded-chart" role="dialog" aria-modal="true" aria-label={expanded.title} onClick={e => e.stopPropagation()}><button className="icon-button close-chart" aria-label="Close expanded chart" onClick={() => setExpanded(null)}><X size={20} /></button><Chart chart={expanded} currency={filters.currency} onExplore={table => { setExpanded(null); explore(table); }} onPlatform={platformFilter} onExpand={setExpanded} /></div></div>}
    {help && <div className="overlay" onClick={() => setHelp(false)}><aside className="drawer wide-drawer" role="dialog" aria-modal="true" aria-label="Definitions and availability" onClick={e => e.stopPropagation()}><div className="drawer-heading"><div><span className="eyebrow">MEASUREMENT CONTRACT</span><h2>Definitions & availability</h2></div><button className="icon-button" aria-label="Close help" onClick={() => setHelp(false)}><X size={20} /></button></div><p className="drawer-description">Published reporting marts support these POC views. The remaining requirements below explain the evidence needed for broader business claims.</p>{readiness.loading && <div className="skeleton table-skeleton" />}{readiness.error && <div className="inline-error">{readiness.error}</div>}{(readiness.data ?? []).map(row => <section className="readiness-item" key={String(row.use_case)}><strong>{String(row.use_case)}</strong><p>{String(row.remaining_requirements)}</p></section>)}</aside></div>}
  </div>;
}

export default function App() {
  const bootstrap = useResource<Bootstrap>('/api/bootstrap');
  const [configure, setConfigure] = useState(false);
  if (bootstrap.error) return <main className="startup-state"><div className="brand-mark"><BarChart3 size={25} /></div><h1>Connect your analytics workspace</h1><p>{bootstrap.error}</p><p>Configure the attached SQL warehouse and dataset permissions for the selected SQL access mode, then verify the Gold connection.</p><button className="button primary" onClick={() => setConfigure(true)}><Database size={15} />Connection settings</button><button className="button secondary" onClick={() => window.location.reload()}><RefreshCw size={15} />Try again</button>{configure && <ConnectionDialog onClose={() => setConfigure(false)} />}</main>;
  if (!bootstrap.data) return <main className="startup-state"><div className="brand-mark"><BarChart3 size={25} /></div><h1>Marketing Intelligence</h1><p>Opening your analytics workspace…</p><RefreshCw size={20} className="spinning" /></main>;
  return <Workspace bootstrap={bootstrap.data} />;
}
