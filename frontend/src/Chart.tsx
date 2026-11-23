import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, LineChart, ScatterChart, FunnelChart, HeatmapChart, CustomChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, MarkLineComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsOption } from 'echarts';
import { Database, Maximize2 } from 'lucide-react';
import { ChartData, format, title } from './api';

const escapeHtml = (value: unknown) => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!);

const colors = ['#168a91', '#6485e4', '#96c8c6', '#b6a0df', '#dfb566'];
echarts.use([BarChart, LineChart, ScatterChart, FunnelChart, HeatmapChart, CustomChart,
  GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, MarkLineComponent, CanvasRenderer]);

export function Chart({ chart, currency, onExplore, onPlatform, onExpand }: {
  chart: ChartData; currency: string; onExplore: (table: string) => void;
  onPlatform: (value: string) => void; onExpand: (chart: ChartData) => void;
}) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current || !chart.rows.length) return;
    const instance = echarts.init(element.current, undefined, { renderer: 'canvas' });
    const data = chart.rows;
    const compactLabel = (v: string) => v.length > 20 ? `${v.slice(0, 18)}…` : v;
    const labels = data.map(row => String(row.label ?? 'Unresolved'));
    const percentage = chart.measures[0]?.format === 'percent';
    const common: EChartsOption = {
      color: colors, textStyle: { fontFamily: 'Inter, sans-serif', color: '#738295', fontSize: 12 },
      animationDuration: 500, grid: { left: 55, right: 22, top: 35, bottom: 48, containLabel: false },
      tooltip: { trigger: 'axis', backgroundColor: '#10243b', borderWidth: 0, textStyle: { color: '#fff', fontSize: 12 },
        valueFormatter: value => format(value, chart.measures[0]?.format, currency) },
      xAxis: { type: 'category', data: labels, boundaryGap: chart.kind !== 'area', axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: '#8491a1', fontSize: 11, margin: 16, formatter: (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(v + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : compactLabel(title(v)) } },
      yAxis: { type: 'value', splitNumber: 4, splitLine: { lineStyle: { color: '#edf1f5', type: 'dashed' } }, axisLabel: {
        color: '#8491a1', formatter: (v: number) => percentage ? `${Math.round(v * 100)}%` : chart.measures[0]?.format === 'percentage_points' ? `${v}%` : format(v, 'compact') } },
      legend: { bottom: 0, icon: 'circle', itemHeight: 7, itemWidth: 7, textStyle: { color: '#6c7b8d', fontSize: 11 } },
    };
    let option: EChartsOption;
    if (chart.kind === 'funnel') {
      option = { ...common, xAxis: undefined, yAxis: undefined, legend: { show: false }, grid: undefined,
        tooltip: { trigger: 'item', formatter: p => `${escapeHtml((p as { name: string }).name)}: ${format((p as { value: number }).value)}` },
        series: [{ type: 'funnel', left: '10%', right: '10%', top: 16, bottom: 5, gap: 5, sort: 'none', minSize: '20%',
          label: { position: 'inside', fontSize: 12, color: '#fff', formatter: '{b}   {c}' },
          itemStyle: { borderWidth: 0, borderRadius: 4 }, data: chart.measures.map((m, i) => ({ name: m.label, value: Number(data[0][m.name]), itemStyle: { color: ['#168a91', '#2c9a9f', '#4dabab', '#6dbbb8', '#8dcac4'][i] } })) }] };
    } else if (chart.kind === 'horizontal') {
      option = { ...common, grid: { left: 100, right: 35, top: 12, bottom: 33 },
        yAxis: { type: 'category', data: labels.map(title), inverse: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { fontSize: 11, width: 88, overflow: 'truncate', color: '#536578' } },
        xAxis: { type: 'value', axisLabel: { fontSize: 11, formatter: (v: number) => format(v, 'compact') }, splitLine: { lineStyle: { color: '#edf1f5', type: 'dashed' } } },
        series: chart.measures.map((m, i) => ({ name: m.label, type: 'bar', barMaxWidth: 16, data: data.map(r => r[m.name] as number),
          itemStyle: { borderRadius: [0, 4, 4, 0], color: colors[i] } })) };
    } else if (chart.kind === 'scatter') {
      option = { ...common, tooltip: { trigger: 'item', formatter: params => {
          const p = params as unknown as { data: { name: string; value: number[] } };
          return `${escapeHtml(p.data.name)}<br/>Spend ${format(p.data.value[0], 'usd')}<br/>Funded accounts ${format(p.data.value[1])}`;
        } }, xAxis: { type: 'value', name: 'Demo spend (USD)', nameLocation: 'middle', nameGap: 29, splitLine: { show: false } },
        yAxis: { type: 'value', name: 'Funded accounts', splitLine: { lineStyle: { type: 'dashed', color: '#e8edf2' } } },
        series: [{ type: 'scatter', symbolSize: 15, itemStyle: { opacity: .72 }, data: data.map(row => ({ name: String(row.label ?? 'Unresolved'), value: chart.measures.map(m => Number(row[m.name])) })) }] };
    } else if (chart.kind === 'heatmap') {
      const x = [...new Set(labels)], y = [...new Set(data.map(row => String(row.group)))];
      option = { ...common, grid: { left: 85, right: 20, top: 15, bottom: 55 }, tooltip: { position: 'top', formatter: params => {
        const v = (params as unknown as { value: number[] }).value; return `${escapeHtml(title(y[v[1]]))} · ${x[v[0]].slice(0, 7)}<br/>${format(v[2], 'percent')}`;
      } }, xAxis: { type: 'category', data: x.map(v => v.slice(0, 7)), axisLine: { show: false }, axisTick: { show: false }, splitArea: { show: false } },
        yAxis: { type: 'category', data: y.map(title), axisLine: { show: false }, axisTick: { show: false } },
        visualMap: { min: 0, max: Math.max(.01, ...data.map(r => Number(r[chart.measures[0].name]))), orient: 'horizontal', left: 'center', bottom: 0, itemHeight: 90, itemWidth: 8,
          inRange: { color: ['#eef8f7', '#99d4cc', '#168a91'] }, show: false },
        series: [{ type: 'heatmap', label: { show: true, fontSize: 12, formatter: p => format((p.value as number[])[2], 'percent') }, itemStyle: { borderWidth: 6, borderColor: '#fff', borderRadius: 7 },
          data: data.map(r => [x.indexOf(String(r.label)), y.indexOf(String(r.group)), Number(r[chart.measures[0].name])]) }] };
    } else if (chart.kind === 'interval') {
      const extent = Math.max(.01, ...data.flatMap(row => ['effect', 'lower', 'upper'].map(key => Math.abs(Number(row[key] ?? 0))))) * 1.2;
      option = { ...common, grid: { left: 85, right: 28, top: 35, bottom: 48 },
        tooltip: { trigger: 'item', formatter: params => {
          const row = data[(params as { dataIndex: number }).dataIndex];
          const points = (value: unknown) => value == null ? 'Unavailable' : `${(Number(value) * 100).toFixed(2)} pp`;
          return `Variant ${escapeHtml(row.label)}<br/>Absolute lift: ${points(row.effect)}<br/>Interval: ${points(row.lower)} to ${points(row.upper)}`;
        } }, xAxis: { type: 'value', min: -extent, max: extent, splitNumber: 4,
          axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(1)} pp`, hideOverlap: true }, splitLine: { lineStyle: { color: '#edf1f5' } } },
        yAxis: { type: 'category', data: labels.map(v => `Variant ${v}`) },
        series: [{ type: 'scatter', symbolSize: 12, data: data.map((r, i) => [Number(r.effect), i]),
          markLine: { silent: true, symbol: 'none', label: { show: false }, lineStyle: { color: '#c2ccd6', type: 'dashed' }, data: [{ xAxis: 0 }] } },
          { type: 'custom', renderItem: (_params, api) => {
            const index = api.value(0) as number, low = api.coord([api.value(1), index]), high = api.coord([api.value(2), index]);
            return { type: 'group', children: [{ type: 'line', shape: { x1: low[0], y1: low[1], x2: high[0], y2: high[1] }, style: { stroke: '#168a91', lineWidth: 2 } },
              ...[low, high].map(point => ({ type: 'line' as const, shape: { x1: point[0], y1: point[1] - 6, x2: point[0], y2: point[1] + 6 }, style: { stroke: '#168a91', lineWidth: 2 } }))] };
          }, data: data.filter(r => r.lower !== null && r.upper !== null).map((r, i) => [i, r.lower, r.upper]) }] };
    } else if (chart.kind === 'waterfall') {
      let running = 0;
      const deltas = chart.measures.map(m => Number(data[0][m.name]));
      const base = deltas.map(value => { const start = Math.min(running, running + value); running += value; return start; });
      option = { ...common, xAxis: { type: 'category', data: [...chart.measures.map(m => m.label), 'Net proxy'], axisTick: { show: false }, axisLine: { show: false } },
        legend: { show: false }, series: [
          { type: 'bar', stack: 'total', itemStyle: { color: 'transparent' }, emphasis: { itemStyle: { color: 'transparent' } }, tooltip: { show: false }, data: [...base, Math.min(0, running)] },
          { type: 'bar', stack: 'total', barMaxWidth: 36, data: [...deltas.map(value => ({ value: Math.abs(value), itemStyle: { color: value >= 0 ? '#168a91' : '#d99a6e' } })), { value: Math.abs(running), itemStyle: { color: '#6485e4' } }], itemStyle: { borderRadius: [4, 4, 0, 0] } }] };
    } else {
      option = { ...common, series: chart.measures.map((m, i) => ({ type: chart.kind === 'bar' ? 'bar' : 'line', name: m.label, data: data.map(row => row[m.name] as number),
        barMaxWidth: 22, smooth: .25, symbol: 'none', lineStyle: { width: 2.5 }, itemStyle: { borderRadius: [4, 4, 0, 0], color: colors[i] },
        areaStyle: chart.kind === 'area' ? { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#168a912f' }, { offset: 1, color: '#168a9102' }]) } : undefined })) };
    }
    instance.setOption(option);
    instance.on('click', params => { if (chart.dimensions[0] === 'platform') onPlatform(String(params.name)); });
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(element.current);
    return () => { observer.disconnect(); instance.dispose(); };
  }, [chart, currency, onPlatform]);
  return <section className="chart-card">
    <div className="panel-heading"><h3>{chart.title}</h3><div className="panel-actions">
      <button className="icon-button" title="Explore supporting data" disabled={!!chart.unavailable_reason} onClick={() => onExplore(chart.table)}><Database size={15} /></button>
      <button className="icon-button" title="Expand chart" onClick={() => onExpand(chart)}><Maximize2 size={15} /></button>
    </div></div>
    {chart.rows.length ? <div ref={element} className="chart-canvas" role="img" aria-label={chart.title} /> : <div className="chart-empty">{chart.unavailable_reason ? `Unavailable for this selection: ${chart.unavailable_reason}` : 'No observations match these filters.'}</div>}
    <p className="chart-note">{chart.note}</p>
  </section>;
}
