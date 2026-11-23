import { useEffect, useRef, useState } from 'react';
import { MessageSquare, RefreshCw, Send } from 'lucide-react';
import { useResource } from './api';

type Result = { title: string; sql: string; columns: string[]; rows: unknown[][]; truncated?: boolean; error?: string };
type Answer = { conversation_id?: string; message_id?: string; conversation_key?: string; status: string; text: string; queries: Result[] };

export function Genie() {
  const config = useResource<{ mode: string; configured: boolean; examples: string[]; space_id: string; auth_mode: 'app' | 'user'; shared_data: boolean }>('/api/genie/config');
  const [question, setQuestion] = useState('');
  const [turns, setTurns] = useState<{ question: string; answer?: Answer }[]>([]);
  const [session, setSession] = useState<{ conversation_id?: string; conversation_key?: string }>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function send(value = question) {
    if (!value.trim() || busy) return;
    controller.current = new AbortController();
    const signal = controller.current.signal;
    setBusy(true); setError(''); setQuestion(''); setStatus('Submitting question');
    setTurns(previous => [...previous, { question: value }]);
    async function read(response: Response): Promise<Answer> {
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Genie request failed.');
      return body;
    }
    try {
      let answer = await read(await fetch('/api/genie/messages', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: value, ...session }), signal }));
      const key = answer.conversation_key ?? session.conversation_key;
      if (answer.conversation_id) setSession({ conversation_id: answer.conversation_id, conversation_key: key });
      let attempts = 0;
      const terminal = ['COMPLETED', 'FAILED', 'CANCELLED', 'QUERY_RESULT_EXPIRED'];
      while (!terminal.includes(answer.status)) {
        if (++attempts > 90) throw new Error('Genie is still processing. Try again later or start a new conversation.');
        setStatus(answer.status.replace(/_/g, ' ').toLowerCase());
        await new Promise(resolve => setTimeout(resolve, 2000));
        if (signal.aborted) return;
        answer = await read(await fetch(`/api/genie/messages/${encodeURIComponent(answer.conversation_id ?? '')}/${encodeURIComponent(answer.message_id ?? '')}?key=${encodeURIComponent(key ?? '')}`, { signal }));
      }
      setTurns(previous => previous.map((turn, i) => i === previous.length - 1 ? { ...turn, answer } : turn));
    } catch (failure) { if (!signal.aborted) setError(failure instanceof Error ? failure.message : 'Genie is unavailable.'); }
    finally { if (!signal.aborted) setBusy(false); }
  }
  const enabled = config.data?.mode === 'preview' || config.data?.configured;
  return <section className="genie-panel">
    <div className="genie-heading"><div><MessageSquare size={23} /><h2>Ask your marketing data</h2></div><button className="button secondary" disabled={busy} onClick={() => { setTurns([]); setSession({}); setError(''); }}>New conversation</button></div>
    <p>{config.data?.mode === 'preview' ? 'Guided sample answers from the source CSV fixture. Live Genie is not connected locally.' : 'Ask questions and follow up using the attached, curated Databricks Genie space.'}</p>
    {config.data?.shared_data && <div className="scope-note">Genie uses the shared app dataset. Conversations are isolated to your browser session and signed-in account.</div>}
    <div className="scope-note">Genie uses its space’s curated tables and instructions. Dashboard filters and Connection Settings do not change that space. Include dates, currencies and the intended business population in your question.</div>
    {!enabled && !config.loading && <div className="inline-error">Attach a Genie Agent with resource key genie-space and grant the configured identity access to its data.</div>}
    <div className="genie-examples">{config.data?.examples.map(example => <button key={example} disabled={busy || !enabled} onClick={() => send(example)}>{example}</button>)}</div>
    <div className="genie-history" aria-live="polite">{turns.map((turn, i) => <article key={i}><div className="genie-question">{turn.question}</div>{turn.answer && <div className="genie-answer"><strong>{config.data?.mode === 'preview' ? 'Sample analytics' : 'Genie'}</strong><p>{turn.answer.text || 'See the SQL and results below.'}</p>{turn.answer.queries.map((result, j) => <section key={j}><h3>{result.title}</h3><details><summary>View generated SQL</summary><pre>{result.sql}</pre></details>{result.error && <p className="inline-error">{result.error}</p>}{result.columns.length > 0 && <div className="table-scroll"><table><thead><tr>{result.columns.map((column, k) => <th key={k}>{column}</th>)}</tr></thead><tbody>{result.rows.map((row, r) => <tr key={r}>{row.map((cell, c) => <td key={c}>{cell === null ? '—' : typeof cell === 'object' ? JSON.stringify(cell) : String(cell)}</td>)}</tr>)}</tbody></table>{!result.rows.length && <p>No matching result rows.</p>}</div>}{result.truncated && <p>Showing the first available result chunk, limited to 100 rows.</p>}</section>)}</div>}</article>)}</div>
    {busy && <p role="status"><RefreshCw size={15} className="spinning" /> {status}…</p>}
    {(error || config.error) && <div className="inline-error" role="alert">{error || config.error}</div>}
    <form className="genie-composer" onSubmit={event => { event.preventDefault(); send(); }}><textarea aria-label="Ask Genie" placeholder="Ask a marketing analytics question…" maxLength={4000} value={question} onChange={event => setQuestion(event.target.value)} disabled={busy || !enabled} /><button className="button primary" disabled={busy || !enabled || !question.trim()}><Send size={16} />Ask Genie</button></form>
  </section>;
}
