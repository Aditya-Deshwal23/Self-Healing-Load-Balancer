"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TimePoint } from "@/lib/types";

type SeriesDefinition = {
  key: "value" | "peer" | "preserved";
  label: string;
  color: string;
  dashed?: boolean;
};

function ChartTooltip({ active, payload, label, unit }: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string; unit: string }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{label}</strong>{payload.map((item) => <span key={item.name}><i style={{ background: item.color }} />{item.name}<code>{item.value}{unit}</code></span>)}</div>;
}

export function EvidenceChart({
  title,
  summary,
  data,
  unit,
  series,
  yDomain,
  actionAt,
  sampleCount,
}: {
  title: string;
  summary: string;
  data: TimePoint[];
  unit: string;
  series: SeriesDefinition[];
  yDomain?: [number, number];
  actionAt?: string;
  sampleCount: number;
}) {
  return (
    <figure className="evidence-chart">
      <figcaption>
        <div><strong>{title}</strong><span>{summary}</span></div>
        <div className="chart-meta"><span>{unit || "count"}</span><span>2 min</span><span>IST</span><span>{sampleCount.toLocaleString()} samples</span></div>
      </figcaption>
      <div className="chart-legend" aria-hidden="true">{series.map((item) => <span key={item.key}><i style={{ background: item.color }} />{item.label}</span>)}</div>
      <div className="chart-canvas" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
            <XAxis dataKey="time" tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis domain={yDomain ?? ["auto", "auto"]} tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickLine={false} axisLine={false} width={46} />
            <Tooltip content={<ChartTooltip unit={unit} />} />
            {actionAt && <ReferenceLine x={actionAt} stroke="var(--accent-copper)" strokeDasharray="3 3" label={{ value: "action", fill: "var(--text-muted)", fontSize: 10, position: "insideTopRight" }} />}
            {series.map((item) => <Line key={item.key} name={item.label} type="linear" dataKey={item.key} stroke={item.color} strokeWidth={2} strokeDasharray={item.dashed ? "4 4" : undefined} dot={false} activeDot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="sr-only">{summary}</p>
      <details className="accessible-alternative chart-table"><summary>View chart data</summary><div className="table-scroll"><table><thead><tr><th>Time (IST)</th>{series.map((item) => <th key={item.key}>{item.label} ({unit || "count"})</th>)}</tr></thead><tbody>{data.map((point) => <tr key={point.time}><th>{point.time}</th>{series.map((item) => <td className="mono" key={item.key}>{point[item.key] ?? "Missing"}</td>)}</tr>)}</tbody></table></div></details>
    </figure>
  );
}

export function IntervalPlot({
  data,
}: {
  data: Array<{ name: string; median: number; low: number; high: number; success: number; retry: number; trials: number }>;
}) {
  return (
    <figure className="interval-plot">
      <figcaption><strong>Healthy route capacity preserved</strong><span>Median and bootstrap interval by matched baseline · % · 30 trials each</span></figcaption>
      <div className="interval-axis" aria-hidden="true"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div>
      <div className="interval-rows" aria-hidden="true">
        {data.map((item) => <div className="interval-row" key={item.name}><span>{item.name}</span><div className="interval-track"><i className="interval-range" style={{ left: `${item.low}%`, width: `${item.high - item.low}%` }} /><i className="interval-median" style={{ left: `${item.median}%` }} /></div><code>{item.median}%</code></div>)}
      </div>
      <details className="accessible-alternative"><summary>View comparison data</summary><table><thead><tr><th>Baseline</th><th>Median HCP</th><th>Interval</th><th>Success</th><th>Retry amplification</th><th>Trials</th></tr></thead><tbody>{data.map((item) => <tr key={item.name}><th>{item.name}</th><td>{item.median}%</td><td>{item.low}–{item.high}%</td><td>{item.success}%</td><td>{item.retry}×</td><td>{item.trials}</td></tr>)}</tbody></table></details>
    </figure>
  );
}
