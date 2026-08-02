"use client";

import {
  AlertTriangle,
  Box,
  Check,
  ChevronDown,
  CircleDashed,
  Eye,
  GitCompareArrows,
  Layers3,
  LocateFixed,
  LockKeyhole,
  Network,
  Pause,
  Server,
  Workflow,
} from "lucide-react";
import { useState, type CSSProperties } from "react";
import { useDemoSnapshot } from "@/lib/demo/provider";
import { StatusTag } from "@/components/ui";

type TopologyMode = "observed" | "desired" | "compare";

export function LiveTopology({ compact = false }: { compact?: boolean }) {
  const { instances, routes } = useDemoSnapshot();
  const [isolatedRoute, setIsolatedRoute] = useState(compact ? "checkout" : "all");
  const [mode, setMode] = useState<TopologyMode>("compare");
  const [frozen, setFrozen] = useState(false);
  const [listMode, setListMode] = useState(false);

  const activeRoutes = compact ? routes.slice(0, 4) : routes;

  return (
    <div className={`topology-module ${compact ? "compact" : ""}`}>
      {!compact && (
        <div className="topology-toolbar">
          <div className="toolbar-group">
            <label><span>Isolate route</span><select value={isolatedRoute} onChange={(event) => setIsolatedRoute(event.target.value)}><option value="all">All configured routes</option>{routes.map((route) => <option value={route.id} key={route.id}>{route.label}</option>)}</select><ChevronDown size={13} /></label>
            <button className="button secondary compact" type="button" onClick={() => setIsolatedRoute("checkout")}><LocateFixed size={14} />Zoom to incident</button>
          </div>
          <div className="toolbar-group">
            <div className="segmented-control" aria-label="Topology state">{(["observed", "desired", "compare"] as const).map((item) => <button type="button" aria-pressed={mode === item} className={mode === item ? "active" : ""} onClick={() => setMode(item)} key={item}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div>
            <button className={`button secondary compact ${frozen ? "active" : ""}`} type="button" aria-pressed={frozen} onClick={() => setFrozen((value) => !value)}><Pause size={14} />{frozen ? "Frozen at 22:02:14" : "Freeze at incident"}</button>
            <button className="button secondary compact" type="button" aria-pressed={listMode} onClick={() => setListMode((value) => !value)}><Eye size={14} />{listMode ? "Canvas" : "List alternative"}</button>
          </div>
        </div>
      )}

      {listMode ? <TopologyList /> : (
        <div className={`topology-canvas mode-${mode} ${frozen ? "frozen" : ""}`} aria-label="Traffic topology visualization" role="img">
          <div className="topology-column edge-column">
            <span className="topology-label">EDGE</span>
            <TopologyNode icon={Network} title="NGINX" detail="TLS · request IDs" state="ready" size="medium" />
          </div>
          <div className="topology-arrow primary-flow" aria-hidden="true"><span>159 req/s</span><i /></div>
          <div className="topology-column proxy-column">
            <span className="topology-label">DATA PLANE</span>
            <TopologyNode icon={Workflow} title="HAProxy" detail="fe_application" state="ready" size="large" />
          </div>
          <div className="topology-bus route-bus" aria-hidden="true" />
          <div className="topology-column pools-column">
            <span className="topology-label">LOGICAL POOLS</span>
            {activeRoutes.map((route) => {
              const focused = isolatedRoute === "all" || isolatedRoute === route.id;
              const incident = route.id === "checkout";
              return <div className={`pool-flow ${focused ? "focused" : "dimmed"} ${incident ? "incident" : ""}`} style={{ "--edge-weight": `${Math.max(2, route.requestsPerSecond / 18)}px` } as CSSProperties} key={route.id}><span className="flow-line" aria-hidden="true" /><div className="pool-node"><span><Layers3 size={14} />{route.label}</span><code>{route.backend}</code><small>{route.requestsPerSecond} req/s · {route.criticality}</small>{incident && <em>1 member quarantined</em>}</div><span className="flow-line outbound" aria-hidden="true" /></div>;
            })}
          </div>
          <div className="topology-bus instance-bus" aria-hidden="true" />
          <div className="topology-column instances-column">
            <span className="topology-label">PHYSICAL INSTANCES</span>
            {instances.map((instance) => <TopologyNode key={instance.id} icon={Server} title={instance.label} detail={`${instance.version} · cap ${instance.capacity}`} state={instance.id === "inst-b" ? "scoped" : instance.probe === "unknown" ? "unknown" : "ready"} size={instance.utilization > 68 ? "large" : "medium"} annotation={instance.id === "inst-b" ? "checkout only · other routes eligible" : `${instance.utilization}% physical load`} drift={instance.id === "inst-c"} />)}
          </div>
          <div className="topology-arrow dependency-flow" aria-hidden="true"><i /><span>upstream calls</span></div>
          <div className="topology-column dependency-column">
            <span className="topology-label">DEPENDENCIES</span>
            <TopologyNode icon={Box} title="Application" detail="route-specific work" state="ready" size="medium" />
            <TopologyNode icon={LockKeyhole} title="Shared services" detail="bounded evidence only" state="unknown" size="small" />
          </div>
          <div className="topology-legend"><span><i className="edge-thin" />low request rate</span><span><i className="edge-thick" />high request rate</span><span><i className="edge-dashed" />desired / observed mismatch</span><span><span className="node-scale small" /><span className="node-scale large" />node size = capacity</span></div>
        </div>
      )}
      {compact && <div className="topology-compact-foot"><span><AlertTriangle size={14} />Incident focus: <code>/checkout × Backend B</code></span><span>Backend B remains one physical node with four pool edges.</span></div>}
    </div>
  );
}

function TopologyNode({
  icon: Icon,
  title,
  detail,
  state,
  size,
  annotation,
  drift,
}: {
  icon: typeof Server;
  title: string;
  detail: string;
  state: "ready" | "scoped" | "unknown";
  size: "small" | "medium" | "large";
  annotation?: string;
  drift?: boolean;
}) {
  return <div className={`topology-node state-${state} node-${size} ${drift ? "drift" : ""}`}><div className="node-icon"><Icon size={17} aria-hidden="true" /></div><div><strong>{title}</strong><code>{detail}</code>{annotation && <small>{annotation}</small>}</div><span className="node-state">{state === "ready" ? <><Check size={12} />ready</> : state === "scoped" ? <><AlertTriangle size={12} />route-local</> : <><CircleDashed size={12} />unknown</>}</span>{drift && <em><GitCompareArrows size={11} />weight drift</em>}</div>;
}

function TopologyList() {
  const { instances, routes } = useDemoSnapshot();
  return (
    <div className="topology-list" aria-label="Accessible traffic topology hierarchy">
      <ol>
        <li><div><Network size={16} /><strong>NGINX edge</strong><StatusTag tone="success">Ready</StatusTag></div><p>Terminates TLS and forwards application traffic directly to HAProxy.</p>
          <ol><li><div><Workflow size={16} /><strong>HAProxy fe_application</strong><StatusTag tone="success">Ready</StatusTag></div><p>Matches one configured route group before selecting a logical pool member.</p>
            <ol>{routes.map((route) => <li key={route.id}><div><Layers3 size={16} /><strong>{route.label} pool</strong><span className="mono">{route.requestsPerSecond} req/s</span></div><p>{route.id === "checkout" ? "Backend B membership is quarantined; A and C remain eligible." : "Backend A, B, and C are independently addressable memberships where registered."}</p></li>)}</ol>
          </li></ol>
        </li>
      </ol>
      <section><h3>Physical instances, represented once</h3>{instances.map((instance) => <div className="topology-list-instance" key={instance.id}><Server size={16} /><span><strong>{instance.label}</strong><small>{instance.version} · physical capacity {instance.capacity} · {instance.utilization}% load</small></span>{instance.id === "inst-b" ? <StatusTag tone="warning">1 of 4 quarantined</StatusTag> : <StatusTag tone={instance.probe === "unknown" ? "neutral" : "success"}>{instance.probe}</StatusTag>}</div>)}</section>
    </div>
  );
}
