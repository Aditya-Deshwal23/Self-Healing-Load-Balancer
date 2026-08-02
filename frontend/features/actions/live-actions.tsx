"use client";

import Link from "next/link";
import { ArrowRight, Check, CircleDashed } from "lucide-react";
import { useAction, useActions } from "@/lib/api/operations";
import {
  KeyValueGrid,
  PageHeader,
  Panel,
  StateMessage,
  StatusTag,
} from "@/components/ui";

function tone(value: string) {
  return ["COMMITTED", "CONFIRMED", "EFFECTIVE"].includes(value)
    ? ("success" as const)
    : ["FAILED", "HARMFUL", "ROLLBACK_FAILED"].includes(value)
      ? ("danger" as const)
      : [
            "PREPARED",
            "APPLYING",
            "APPLIED",
            "VERIFYING",
            "ACKNOWLEDGMENT_LOST",
          ].includes(value)
        ? ("warning" as const)
        : ("neutral" as const);
}

export function LiveActions({ actionId }: { actionId?: string }) {
  const list = useActions();
  const selectedId = actionId ?? list.data?.items[0]?.id;
  const detail = useAction(actionId ? selectedId : undefined);
  if (list.isLoading)
    return (
      <StateMessage state="loading" title="Loading durable actions…">
        Reading prepared intent and Runtime attempts.
      </StateMessage>
    );
  if (list.isError || !list.data)
    return (
      <StateMessage state="failure" title="Actions are unavailable.">
        No fixture actions were substituted.
      </StateMessage>
    );
  if (actionId) {
    if (detail.isLoading)
      return (
        <StateMessage state="loading" title="Loading action readback…">
          Joining intent, attempts, and verification.
        </StateMessage>
      );
    if (detail.isError || !detail.data)
      return (
        <StateMessage state="failure" title="Action unavailable.">
          The durable action could not be loaded.
        </StateMessage>
      );
    const action = detail.data;
    const latestVerification = action.verification?.at(-1);
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="Action details"
          title={`${action.kind} · ${action.target.backend}/${action.target.server}`}
          brief="The lifecycle below is durable: intent was committed before mutation, and application was confirmed only after HAProxy Runtime readback."
          meta={
            <>
              <StatusTag tone={tone(action.lifecycle)}>
                {action.lifecycle}
              </StatusTag>
              <code>{action.id}</code>
            </>
          }
          actions={
            <Link className="button secondary" href="/app/actions">
              All actions
            </Link>
          }
        />
        <Panel
          title="Requested versus observed"
          kicker="Absolute, idempotent operation"
        >
          <KeyValueGrid
            items={[
              {
                label: "Previous desired",
                value: `${String(action.previous_desired.admin_state ?? action.previous_desired.admin)} · w ${String(action.previous_desired.weight)}`,
              },
              {
                label: "Previous observed",
                value: `${String(action.previous_observed.admin_state ?? action.previous_observed.admin)} · w ${String(action.previous_observed.weight)}`,
              },
              {
                label: "Requested",
                value: `${String(action.requested_state.admin_state ?? action.requested_state.admin)} · w ${String(action.requested_state.weight)}`,
              },
              {
                label: "Generation",
                value: String(action.controller_generation),
                mono: true,
              },
              {
                label: "Expiry",
                value: new Date(action.expires_at).toLocaleString(),
                mono: true,
              },
              {
                label: "Rollback",
                value: JSON.stringify(action.rollback_strategy),
                mono: true,
              },
            ]}
          />
        </Panel>
        <Panel title="Action attempts" kicker="Runtime command and readback">
          <ol className="attempt-list">
            {action.attempts.map((attempt) => (
              <li key={attempt.id}>
                {attempt.status === "CONFIRMED" ? (
                  <Check size={15} />
                ) : (
                  <CircleDashed size={15} />
                )}
                <div>
                  <strong>
                    Attempt {attempt.sequence} · {attempt.operation}
                  </strong>
                  <span>
                    <StatusTag tone={tone(attempt.status)}>
                      {attempt.status}
                    </StatusTag>{" "}
                    issued {new Date(attempt.issued_at).toLocaleString()}
                  </span>
                  <details>
                    <summary>Exact response and observed state</summary>
                    <pre>
                      {JSON.stringify(
                        {
                          response: attempt.response,
                          observed: attempt.observed_state,
                          error_code: attempt.error_code,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                </div>
              </li>
            ))}
          </ol>
        </Panel>
        <Panel
          title="Verification obligations"
          kicker="Affected relief and preservation"
        >
          {latestVerification ? (
            <div className="verification-columns">
              <article>
                <span>Affected symptom</span>
                <StatusTag tone={tone(latestVerification.result)}>
                  {latestVerification.result}
                </StatusTag>
                <pre>
                  {JSON.stringify(latestVerification.affected, null, 2)}
                </pre>
              </article>
              <article>
                <span>Unaffected preservation</span>
                <strong>{latestVerification.sample_count} real samples</strong>
                <pre>
                  {JSON.stringify(latestVerification.preservation, null, 2)}
                </pre>
              </article>
            </div>
          ) : (
            <StateMessage state="unknown" title="Verification still collecting">
              Zero samples never count as success.
            </StateMessage>
          )}
        </Panel>
      </div>
    );
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Actions"
        title="Durable healing actions"
        brief="Only the authorized worker can mutate HAProxy. Each action keeps its evidence certificate, generation, previous state, attempt, readback, and rollback strategy."
      />
      {!list.data.items.length ? (
        <StateMessage state="empty" title="No actions recorded">
          Healthy operation requires no mutation.
        </StateMessage>
      ) : (
        <section className="panel table-panel">
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Lifecycle</th>
                  <th>Target</th>
                  <th>Intent</th>
                  <th>Generation</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((action) => (
                  <tr key={action.id}>
                    <td>
                      <StatusTag tone={tone(action.lifecycle)}>
                        {action.lifecycle}
                      </StatusTag>
                    </td>
                    <td>
                      <code>
                        {action.target.backend}/{action.target.server}
                      </code>
                    </td>
                    <td>
                      <strong>
                        {String(
                          action.requested_state.admin_state ??
                            action.requested_state.admin,
                        )}{" "}
                        · weight {String(action.requested_state.weight)}
                      </strong>
                      <small>{action.expected_effect}</small>
                    </td>
                    <td>
                      <code>{action.controller_generation}</code>
                    </td>
                    <td>
                      <Link
                        className="inline-link"
                        href={`/app/actions?action=${action.id}`}
                      >
                        Readback
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
