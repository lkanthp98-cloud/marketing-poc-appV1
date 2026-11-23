import { useEffect, useState } from 'react';

export type Row = Record<string, unknown>;
export type DataLayer = 'gold' | 'use_cases';
export type Filters = { start: string; end: string; campaign: string; platform: string; product: string; market: string; currency: string; plan: string; compare: boolean };
export type TableInfo = { name: string; kind: string; grain: string; rows: number | null; note: string; sources: string; location: string };
export type Bootstrap = {
  mode: string; viewer: string; catalog: string; schema: string; tables: TableInfo[]; sources: number | null;
  sql_auth_mode: 'app' | 'user'; shared_data: boolean;
  filter_status?: Record<string, { state: 'available' | 'empty' | 'unavailable'; message: string; sources: string[]; errors: string[] }>;
  source_mode: 'gold' | 'use_cases' | 'both'; enabled_sources: DataLayer[]; analytics_layer: DataLayer; warnings: string[];
  analytics_catalog: string; analytics_schema: string; use_case_tables: TableInfo[];
  dates: { start: string; end: string }; campaigns: { campaign_key: string; campaign_name: string }[];
  platforms: string[]; products: string[]; markets: string[]; currencies: string[]; plans: string[];
};
export type Metric = { label: string; value: number | null; format: string; description: string; table: string;
  unavailable_reason?: string | null;
  source: string;
  change: number | null; previous: number | null; direction: string; unsupported_filters: string[] };
export type ChartData = { title: string; kind: string; table: string; dimensions: string[];
  unavailable_reason?: string | null;
  source: string;
  measures: { name: string; label: string; format: string }[]; note: string; rows: Row[]; unsupported_filters: string[] };
export type Dashboard = { title: string; subtitle: string; eyebrow: string; metrics: Metric[]; charts: ChartData[]; table: string; mode: string };
export type TableData = { name: string; source: string; schema: { name: string; type: string }[]; rows: Row[]; total: number; page: number; size: number; unsupported_filters: string[] };

export function query(filters: Filters): string {
  return new URLSearchParams(Object.entries(filters).map(([key, value]) => [key, String(value)])).toString();
}

export function useResource<T>(path: string | null, revision = 0, keepDataOnError = false) {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: string }>({ data: null, loading: true, error: '' });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setState(previous => ({ ...previous, loading: true, error: '' }));
    fetch(path, { signal: controller.signal }).then(async response => {
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}).`);
      }
      return response.json() as Promise<T>;
    }).then(data => setState({ data, loading: false, error: '' })).catch(error => {
      if (error.name !== 'AbortError') setState(previous => ({ data: keepDataOnError ? previous.data : null, loading: false, error: error.message }));
    });
    return () => controller.abort();
  }, [path, revision, keepDataOnError]);
  return state;
}

export function format(value: unknown, kind = 'number', currency = 'USD', compact = false): string {
  if (value === null || value === undefined || (typeof value === 'number' && !Number.isFinite(value))) return '—';
  if (typeof value !== 'number') return typeof value === 'object' ? JSON.stringify(value) : String(value);
  if (kind === 'percent') return new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 1 }).format(value);
  if (kind === 'percentage_points') return `${value.toFixed(1)}%`;
  if (kind === 'currency' || kind === 'usd') {
    const unit = kind === 'usd' ? 'USD' : currency || 'USD';
    try { return new Intl.NumberFormat('en-US', {
      style: 'currency', currency: unit,
      notation: compact && Math.abs(value) >= 100000 ? 'compact' : 'standard', maximumFractionDigits: compact ? 1 : 2,
    }).format(value); } catch { return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value)} ${unit}`; }
  }
  return new Intl.NumberFormat('en-US', { notation: kind === 'compact' || compact ? 'compact' : 'standard', maximumFractionDigits: 1 }).format(value);
}

export function title(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());
}
