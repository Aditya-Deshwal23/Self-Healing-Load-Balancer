"use client";

import Link from "next/link";
import { ArrowRight, Check, CircleDashed } from "lucide-react";
import { useRecoveries, useRecovery } from "@/lib/api/operations";
import {
  PageHeader,
  Panel,
  ProgressBar,
  StateMessage,
  StatusTag,
} from "@/components/ui";

function tone(value: string) {
  return ["COMPLETED", "VERIFIED", "HEALTHY"].includes(value)
    ? ("success" as const)
    : ["FAILED", "NEEDS_REVIEW", "ROLLED_BACK"].includes(value)
      ? ("danger" as const)
      : ["RUNNING", "CURRENT", "PROBING"].includes(value)
        ? ("warning" as const)
        : ("neutral" as const);
}

export function LiveRecovery({ runId }: { runId?: string }) {
  const list = useRecoveries();
  const selectedId = runId ?? list.data?.items[0]?.id;
  const detail = useRecovery(runId ? selectedId : undefined);
  if (list.isLoading)
    return (
      <StateMessage state="loading" title="Loading staged recovery…">
        Reading durable reintegration runs.
      </StateMessage>
    );
  if (list.isError || !list.data)
    return (
      <StateMessage state="failure" title="Recovery data unavailable.">
        No simulated stages were substituted.
      </StateMessage>
    );
  if (runId) {
    if (detail.isLoading)
      return (
        <StateMessage state="loading" title="Loading recovery stages…">
          Each stage is sample- and readback-gated.
        </StateMessage>
      );
    if (detail.isError || !detail.data)
      return (
        <StateMessage state="failure" title="Reintegration run unavailable.">
          The selected run could not be loaded.
        </StateMessage>
      );
    const run = detail.data;
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="Recovery / Reintegration"
          title={`${run.current_stage} · ${run.status}`}
          brief="A cleared fault does not immediately restore full traffic. The worker probes first, then advances 5% → 20% → 50% → 100% with real samples and Runtime readback at every stage."
          meta={
            <>
              <StatusTag tone={tone(run.status)}>{run.status}</StatusTag>
              <code>{run.id}</code>
              <span>
                {run.retry_count}/{run.maximum_retries} retries
              </span>
            </>
          }
          actions={
            <Link className="button secondary" href="/app/reintegration">
              All runs
            </Link>
          }
        />
        <Panel
          title="Evidence-gated stages"
          kicker="Last verified state is the rollback target"
        >
          <ol className="recovery-stage-list">
            {run.stages.map((stage) => (
              <li className={stage.status.toLowerCase()} key={stage.id}>
                {stage.status === "VERIFIED" ? (
                  <Check size={15} />
                ) : (
                  <CircleDashed size={15} />
                )}
                <div>
                  <span>
                    <strong>{stage.name}</strong>
                    <StatusTag tone={tone(stage.status)}>
                      {stage.status}
                    </StatusTag>
                  </span>
                  <small>
                    requested w {stage.requested_weight ?? "probe"} · observed w{" "}
                    {stage.observed_weight ?? "—"}
                  </small>
                  <ProgressBar
                    value={stage.sample_count}
                    max={Math.max(stage.minimum_samples, stage.sample_count)}
                    label="Real samples"
                    tone={stage.status === "VERIFIED" ? "success" : "warning"}
                  />
                </div>
              </li>
            ))}
          </ol>
        </Panel>
      </div>
    );
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Recovery"
        title="Reintegration runs"
        brief="Memberships recover conservatively through PROBING, 5%, 20%, 50%, 100%, and HEALTHY. Failed evidence returns traffic to the last verified stage or quarantine."
      />
      {!list.data.items.length ? (
        <StateMessage state="empty" title="No membership is recovering">
          The route matrix is fully eligible.
        </StateMessage>
      ) : (
        <section className="panel table-panel">
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Current stage</th>
                  <th>Last verified</th>
                  <th>Retries</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <StatusTag tone={tone(run.status)}>
                        {run.status}
                      </StatusTag>
                    </td>
                    <td>
                      <strong>{run.current_stage}</strong>
                      <small>
                        <code>{run.id.slice(0, 8)}</code>
                      </small>
                    </td>
                    <td>{run.last_verified_stage}</td>
                    <td>
                      {run.retry_count}/{run.maximum_retries}
                    </td>
                    <td>
                      <Link
                        className="inline-link"
                        href={`/app/reintegration?run=${run.id}`}
                      >
                        Stages
                        <ArrowRight size={13} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
