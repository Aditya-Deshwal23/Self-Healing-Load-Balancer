"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTrafficHistory } from "@/lib/api/operations";
import { Panel, StateMessage } from "@/components/ui";

const routes = [
  { key: "public", label: "/public", color: "#297c62" },
  { key: "auth", label: "/auth", color: "#a25d00" },
  { key: "catalog", label: "/catalog", color: "#6256a5" },
  { key: "checkout", label: "/checkout", color: "#b1483c" },
];

type MetricKey = "requests_per_second" | "error_rate" | "worst_instance_p95_ms";

function TrafficLinePanel({
  title,
  description,
  metric,
  unit,
}: {
  title: string;
  description: string;
  metric: MetricKey;
  unit: string;
}) {
  const query = useTrafficHistory();
  const data = useMemo(
    () => (query.data?.points ?? []).map((point) => {
      const row: Record<string, string | number | null> = {
        time: new Date(point.at).toLocaleTimeString([], { minute: "2-digit", second: "2-digit" }),
      };
      for (const route of routes) {
        const value = point.routes[route.key]?.[metric] ?? null;
        row[route.key] = metric === "error_rate" && value !== null ? value * 100 : value;
      }
      return row;
    }),
    [metric, query.data?.points],
  );

  if (query.isLoading) {
    return <Panel title={title} kicker="Last 2 minutes"><StateMessage state="loading" title="Loading traffic history…">Reading persisted observation windows.</StateMessage></Panel>;
  }
  if (query.isError || !query.data) {
    return <Panel title={title} kicker="Last 2 minutes"><StateMessage state="failure" title="Traffic history is unavailable.">The live snapshot remains available in the route matrix.</StateMessage></Panel>;
  }

  return (
    <Panel title={title} kicker="Last 2 minutes" className="traffic-history-panel">
      <figure className="traffic-history-chart">
        <figcaption>{description}</figcaption>
        {data.length ? (
          <>
            <div className="traffic-chart-legend" aria-label="Routes">
              {routes.map((route) => <span key={route.key}><i style={{ background: route.color }} />{route.label}</span>)}
            </div>
            <div className="traffic-chart-canvas">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                  <CartesianGrid stroke="var(--border-subtle)" vertical={false} />
                  <XAxis dataKey="time" minTickGap={28} tick={{ fill: "var(--text-muted)", fontSize: 9 }} tickLine={false} axisLine={false} />
                  <YAxis width={42} tick={{ fill: "var(--text-muted)", fontSize: 9 }} tickLine={false} axisLine={false} />
                  <Tooltip content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    return <div className="chart-tooltip"><strong>{label}</strong>{payload.map((item) => <span key={String(item.dataKey)}><i style={{ background: String(item.color) }} />{String(item.name)}<code>{typeof item.value === "number" ? item.value.toFixed(metric === "error_rate" ? 1 : 2) : "—"}{unit}</code></span>)}</div>;
                  }} />
                  {routes.map((route) => <Line key={route.key} name={route.label} dataKey={route.key} type="monotone" stroke={route.color} strokeWidth={2} dot={false} activeDot={{ r: 3 }} connectNulls isAnimationActive={false} />)}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="traffic-chart-note">Five-second averages of rolling {query.data.observation_window_seconds}-second evidence windows. Request/error volume is combined across three instances; latency shows the slowest instance p95.</p>
          </>
        ) : (
          <StateMessage state="empty" title="Collecting enough history">Charts appear as the worker persists live observation windows.</StateMessage>
        )}
      </figure>
    </Panel>
  );
}

export function TrafficHistoryCharts() {
  return (
    <section className="traffic-history-grid" aria-label="Endpoint traffic trends">
      <TrafficLinePanel title="Requests by endpoint" description="Request rate across all backends." metric="requests_per_second" unit=" req/s" />
      <TrafficLinePanel title="HTTP 5xx rate by endpoint" description="Share of responses returning HTTP 5xx." metric="error_rate" unit="%" />
      <TrafficLinePanel title="Slowest backend p95" description="Worst backend p95 latency for each endpoint." metric="worst_instance_p95_ms" unit=" ms" />
    </section>
  );
}
