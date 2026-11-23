import { useEffect, useRef, useState } from 'react';
import { Database, RefreshCw, X } from 'lucide-react';
import { useResource } from './api';

type Profile = { source_mode: 'gold' | 'use_cases' | 'both'; gold_catalog: string; gold_schema: string; use_cases_catalog: string; use_cases_schema: string };

export function ConnectionDialog({ onClose }: { onClose: () => void }) {
  const settings = useResource<{ mode: string; connection: Profile; sql_auth_mode: 'app' | 'user'; shared_data: boolean }>('/api/connection');
  const [profile, setProfile] = useState<Profile>({ source_mode: 'gold', gold_catalog: '', gold_schema: '', use_cases_catalog: '', use_cases_schema: '' });
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
    <p>Connect your Gold catalog and schema. All use-case analytics and the Gold explorer read this foundation using the attached SQL warehouse.</p>
    {settings.data?.mode === 'live' && <div className="scope-note">{settings.data.shared_data ? 'Shared app access: approved app users see the same configured dataset through the app service principal. The schema is set by the deployment.' : 'User access: SQL uses your Databricks identity and table permissions.'}</div>}
    {settings.data?.mode === 'preview' && <div className="scope-note">Sample mode uses source-derived local data. Live connections become available after deployment with DATA_MODE=live.</div>}
    <div className="connection-fields">{([['gold_catalog', 'Gold catalog'], ['gold_schema', 'Gold schema']] as const).map(([key, label]) =>
      <label key={key}>{label}<input aria-label={label} maxLength={255} disabled={busy} readOnly={settings.data?.shared_data} value={profile[key]} onChange={event => setProfile(value => ({ ...value, [key]: event.target.value }))} /></label>)}</div>
    <p className="metadata-description">The app builds the use-case pages directly from published Gold marts and dimensions. Missing datasets or unsupported campaign/platform filters show an explanation. This connection creates no tables.</p>
    {(error || settings.error) && <div className="inline-error" role="alert">{error || settings.error}</div>}
    <button className="button primary" disabled={busy || settings.data?.mode !== 'live'} onClick={connect}>{busy ? <RefreshCw size={16} className="spinning" /> : <Database size={16} />}{busy ? 'Checking access and columns…' : 'Verify & connect'}</button>
  </div></div>;
}
