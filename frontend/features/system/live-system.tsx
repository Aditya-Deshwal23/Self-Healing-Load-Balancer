"use client";

import { Check, CircleDashed, LockKeyhole, Network } from "lucide-react";
import { useOperationalSummary } from "@/lib/api/operations";
import { useControlPlane } from "@/lib/use-control-plane";
import {
  KeyValueGrid,
  PageHeader,
  Panel,
  StateMessage,
  StatusTag,
} from "@/components/ui";

export function LiveSystem() {
  const control = useControlPlane();
  const summary = useOperationalSummary();
  if (summary.isLoading)
    return (
      <StateMessage state="loading" title="Checking system boundaries…">
        Reading the worker generation and control status.
      </StateMessage>
    );
  if (
    summary.isError ||
    !summary.data ||
    !control.status ||
    !control.capabilities
  )
    return (
      <StateMessage state="failure" title="System status unavailable.">
        The console will not infer health from fixture data.
      </StateMessage>
    );
  const capabilities = control.capabilities;
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="System"
        title="Rules-only control-plane status"
        brief="PostgreSQL is durable truth, Redis coordinates events and the worker lease, and exactly one worker owns HAProxy Runtime authority. The browser and API have no Runtime socket."
        meta={
          <>
            <StatusTag
              tone={
                summary.data.worker.status === "ACTIVE" ? "success" : "warning"
              }
            >
              {summary.data.worker.status}
            </StatusTag>
            <span>generation {summary.data.worker.generation ?? "—"}</span>
            <span>SSE {control.streamState}</span>
          </>
        }
      />
      <div className="system-grid">
        <Panel title="Environment" kicker="Current authority">
          <KeyValueGrid
            items={[
              { label: "Name", value: control.status.environment.name },
              {
                label: "Kind",
                value: control.status.environment.kind,
                mono: true,
              },
              {
                label: "Mode",
                value: control.status.environment.mode,
                mono: true,
              },
              {
                label: "Worker heartbeat",
                value: summary.data.worker.last_heartbeat_at
                  ? new Date(
                      summary.data.worker.last_heartbeat_at,
                    ).toLocaleString()
                  : "Unavailable",
                mono: true,
              },
              {
                label: "Control authority",
                value: control.status.control_plane.control_authority,
              },
              {
                label: "HAProxy access",
                value: control.status.control_plane.haproxy_access
                  ? "Exposed to API"
                  : "Worker only",
              },
            ]}
          />
        </Panel>
        <Panel title="Network boundaries" kicker="Published surface">
          <ul className="boundary-list">
            <li>
              <Network size={16} />
              <span>
                <strong>NGINX only</strong>
                <small>0.0.0.0:8080 redirect · 0.0.0.0:8443 HTTPS</small>
              </span>
            </li>
            <li>
              <LockKeyhole size={16} />
              <span>
                <strong>Private control surfaces</strong>
                <small>
                  PostgreSQL, Redis, Prometheus, HAProxy Runtime/stats, and
                  backend fault endpoints
                </small>
              </span>
            </li>
            <li>
              <Check size={16} />
              <span>
                <strong>Same-origin browser traffic</strong>
                <small>
                  REST and SSE use relative /api paths through NGINX
                </small>
              </span>
            </li>
          </ul>
        </Panel>
      </div>
      <Panel title="Prototype capabilities" kicker={capabilities.phase}>
        <div className="capability-columns">
          <section>
            <h3>Implemented now</h3>
            <ul>
              {capabilities.prototype_support.implemented.map((item) => (
                <li key={item}>
                  <Check size={14} />
                  {item}
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3>Planned or unsupported</h3>
            <ul>
              {capabilities.prototype_support.planned.map((item) => (
                <li key={item}>
                  <CircleDashed size={14} />
                  {item}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </Panel>
    </div>
  );
}
