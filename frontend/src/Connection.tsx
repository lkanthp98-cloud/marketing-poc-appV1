import { useEffect, useRef, useState } from 'react';
import { Database, RefreshCw, X } from 'lucide-react';
import { useResource } from './api';

type Profile = { source_mode: 'gold' | 'use_cases' | 'both'; gold_catalog: string; gold_schema: string; use_cases_catalog: string; use_cases_schema: string };

export function ConnectionDialog({ onClose }: { onClose: () => void }) {
  const settings = useResource<{ mode: string; connection: Profile }>('/api/connection');
  const [profile, setProfile] = useState<Profile>({ source_mode: 'both', gold_catalog: '', gold_schema: '', use_cases_catalog: '', use_cases_schema: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const dialog = useRef<HTMLDivElement>(null);
  useEffect(() => { if (settings.data) setProfile(settings.data.connection); }, [settings.data]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLElement>('button')?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab') return;
      const items = [...(dialog.current?.querySelectorAll<HTMLElement>('input, button:not(:disabled)') ?? [])];
      if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1)?.focus(); }
      if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0]?.focus(); }
    };
    document.addEventListener('keydown', keydown);
    return () => { document.removeEventListener('keydown', keydown); previous?.focus(); };
  }, [onClose]);
  async function connect() {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/connection', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profile) });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Check the catalog and schema names.');
      window.location.reload();
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Connection could not be verified.'); setBusy(false); }
  }
  return <div className="overlay" onClick={onClose}><div ref={dialog} className="connection-dialog" role="dialog" aria-modal="true" aria-label="Live data connection" onClick={event => event.stopPropagation()}>
    <div className="drawer-heading"><div><span className="eyebrow">DATA CONNECTION</span><h2>Connect live data</h2></div><button className="icon-button" aria-label="Close connection settings" onClick={onClose}><X size={20} /></button></div>
    <p>Connect Gold, Use Cases, or both. Only enabled sources are checked and queried. Queries use the attached SQL warehouse and your Databricks permissions.</p>
    <label className="source-mode">Data sources<select aria-label="Data sources" value={profile.source_mode} onChange={event => setProfile(value => ({ ...value, source_mode: event.target.value as Profile['source_mode'] }))}><option value="gold">Gold only</option><option value="use_cases">Use Cases only</option><option value="both">Gold and Use Cases</option></select></label>
    {settings.data?.mode === 'preview' && <div className="scope-note">Sample mode uses source-derived local data. Live connections become available after deployment with DATA_MODE=live.</div>}
    <div className="connection-fields">{([['gold_catalog', 'Gold catalog'], ['gold_schema', 'Gold schema'], ['use_cases_catalog', 'Use Cases catalog'], ['use_cases_schema', 'Use Cases schema']] as const).map(([key, label]) =>
      <label key={key}>{label}<input aria-label={label} maxLength={255} disabled={busy || (profile.source_mode === 'gold' && key.startsWith('use_cases')) || (profile.source_mode === 'use_cases' && key.startsWith('gold'))} value={profile[key]} onChange={event => setProfile(value => ({ ...value, [key]: event.target.value }))} /></label>)}</div>
    <p className="metadata-description">Gold-only dashboards use Gold marts. Use-Cases-only dashboards do not require Gold access. With both enabled, dashboards use Use Cases and the explorer offers both layers. Missing or inaccessible metrics are marked unavailable. No tables or permissions are changed.</p>
    {(error || settings.error) && <div className="inline-error" role="alert">{error || settings.error}</div>}
    <button className="button primary" disabled={busy || settings.data?.mode !== 'live'} onClick={connect}>{busy ? <RefreshCw size={16} className="spinning" /> : <Database size={16} />}{busy ? 'Checking access and columns…' : 'Verify & connect'}</button>
  </div></div>;
}
