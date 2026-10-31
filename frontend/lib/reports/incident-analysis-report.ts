import type { DecisionTraceData, RecoveryDetail } from "@/lib/api/operations";

function json(value: unknown) {
  return JSON.stringify(value ?? null, null, 2);
}

function timestamp(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "Not recorded";
}

function reportOutcome(data: DecisionTraceData) {
  const action = data.action;
  const restoreConfirmed = action?.attempts.some(
    (attempt) =>
      attempt.operation === "restore_instance_after_probe_gate" &&
      attempt.status === "CONFIRMED",
  );
  const recoveryVerified =
    data.recovery?.status === "COMPLETED" ||
    (action?.kind === "INSTANCE_QUARANTINE" &&
      data.verification?.result === "EFFECTIVE" &&
      restoreConfirmed);

  if (
    data.incident.status === "NEEDS_REVIEW" ||
    ["RESULT_UNKNOWN", "NEEDS_REVIEW", "ROLLBACK_FAILED"].includes(
      action?.lifecycle ?? "",
    ) ||
    ["HARMFUL", "INEFFECTIVE"].includes(data.verification?.result ?? "")
  ) {
    return "Needs review";
  }

  if (
    data.incident.status === "RESOLVED" &&
    (!action ||
      (action.lifecycle === "COMMITTED" &&
        data.verification?.result === "EFFECTIVE" &&
        (data.recovery === null || recoveryVerified)))
  ) {
    return "Verified";
  }

  return "In progress";
}

export function buildIncidentAnalysisReport(
  data: DecisionTraceData,
  recovery: RecoveryDetail | null,
  generatedAt = new Date(),
) {
  const classification = data.classifications.at(-1) ?? null;
  const fault = data.lab_fault;
  const action = data.action;
  const outcome = reportOutcome(data);
  const events: Array<{ at: string; label: string }> = [
    { at: fault?.applied_at ?? "", label: `Fault applied: ${fault?.scenario ?? "not correlated"}` },
    { at: data.evidence?.started_at ?? "", label: "Evidence window started" },
    { at: data.incident.opened_at, label: `Incident opened: ${classification?.final_class ?? "unclassified"}` },
    ...(action?.attempts.flatMap((attempt) => [
      { at: attempt.issued_at, label: `Action attempt ${attempt.sequence} issued: ${attempt.operation}` },
      { at: attempt.completed_at ?? "", label: `Action attempt ${attempt.sequence} completed: ${attempt.status}` },
    ]) ?? []),
    { at: data.verification?.completed_at ?? "", label: `Verification: ${data.verification?.result ?? "not recorded"}` },
    ...(recovery?.stages.flatMap((stage) => [
      { at: stage.started_at ?? "", label: `Recovery stage started: ${stage.name}` },
      { at: stage.verified_at ?? "", label: `Recovery stage verified: ${stage.name} (${stage.status})` },
    ]) ?? []),
    { at: fault?.cleared_at ?? "", label: "Fault cleared" },
    { at: data.incident.resolved_at ?? "", label: "Incident resolved" },
  ]
    .filter((event) => event.at)
    .sort((left, right) => Date.parse(left.at) - Date.parse(right.at));

  const lines = [
    `# Incident Analysis Report`,
    "",
    `**Outcome:** ${outcome}  `,
    `**Incident:** ${data.incident.id}  `,
    `**Generated:** ${generatedAt.toLocaleString()}`,
    "",
    "## 1. Run summary",
    "",
    `- **Summary:** ${data.incident.summary}`,
    `- **Incident status:** ${data.incident.status}`,
    `- **Severity:** ${data.incident.severity}`,
    `- **Classification:** ${classification?.final_class ?? "Not recorded"}`,
    `- **Confidence:** ${classification?.confidence.toFixed(2) ?? "Not recorded"}`,
    `- **Evidence completeness:** ${classification ? `${Math.round(classification.completeness * 100)}%` : "Not recorded"}`,
    `- **Opened:** ${timestamp(data.incident.opened_at)}`,
    `- **Resolved:** ${timestamp(data.incident.resolved_at)}`,
    "",
    "## 2. Fault setup",
    "",
    ...(fault
      ? [
          `- **Scenario:** ${fault.scenario}`,
          `- **Fault type:** ${fault.scenario_kind ?? "Not recorded"}`,
          `- **Target:** ${fault.target.route ?? "all routes"} / ${fault.target.instance ?? "all instances"}`,
          `- **Duration:** ${fault.duration_seconds}s`,
          `- **Ground-truth ID:** ${fault.ground_truth_id}`,
          `- **Fault status:** ${fault.status}`,
          `- **Applied:** ${timestamp(fault.applied_at)}`,
          `- **Expired at:** ${timestamp(fault.expires_at)}`,
          `- **Cleared:** ${timestamp(fault.cleared_at)}`,
        ]
      : ["No LAB fault overlapped the recorded evidence window; scenario details are unavailable for this incident."]),
    "",
    "## 3. Evidence observed",
    "",
    ...(data.evidence
      ? [
          `- **Observation window:** ${timestamp(data.evidence.started_at)} to ${timestamp(data.evidence.ended_at)}`,
          `- **Window completeness:** ${Math.round(data.evidence.completeness * 100)}%`,
          `- **Conflicts:** ${data.evidence.conflicts.length ? data.evidence.conflicts.join(", ") : "None recorded"}`,
          `- **Fingerprint:** ${data.fingerprint?.hash ?? "Not recorded"}`,
          "",
          "### Metrics, probes, and conflicts",
          "",
          "```json",
          json({ metrics: data.evidence.metrics, probes: data.evidence.probes, conflicts: data.evidence.conflicts }),
          "```",
        ]
      : ["No evidence window was attached to the incident." ]),
    "",
    "## 4. Decision and safety gate",
    "",
    `- **Controller decision:** ${classification?.final_class ?? "Not recorded"}`,
    `- **Fingerprint contract:** ${data.fingerprint?.schema_version ?? "Not recorded"}`,
    `- **Evidence certificate:** ${data.certificate?.hash ?? "Not recorded"}`,
    "",
    "### Supporting evidence",
    "",
    "```json",
    json(classification?.evidence_support),
    "```",
    "",
    "### Competing hypotheses",
    "",
    "```json",
    json(classification?.competing_hypotheses),
    "```",
    "",
    "### Safety inputs and candidate actions",
    "",
    "```json",
    json({ safety_inputs: data.certificate?.safety_inputs, candidate_actions: data.certificate?.candidate_actions }),
    "```",
    "",
    "## 5. HAProxy action and readback",
    "",
    ...(action
      ? [
          `- **Action ID:** ${action.id}`,
          `- **Action type:** ${action.kind}`,
          `- **Lifecycle:** ${action.lifecycle}`,
          `- **Target:** ${action.target.backend}/${action.target.server}`,
          `- **Requested state:** ${json(action.requested_state)}`,
          `- **Previous desired state:** ${json(action.previous_desired)}`,
          `- **Preservation set:** ${action.preservation_set.join(", ") || "None recorded"}`,
          "",
          "### Attempts and Runtime readback",
          "",
          "```json",
          json(action.attempts.map((attempt) => ({ sequence: attempt.sequence, operation: attempt.operation, status: attempt.status, issued_at: attempt.issued_at, completed_at: attempt.completed_at, error_code: attempt.error_code, response: attempt.response, observed_state: attempt.observed_state }))),
          "```",
        ]
      : ["No HAProxy mutation was recorded. This may be the expected safe result for a non-actionable or ambiguous classification."]),
    "",
    "## 6. Verification",
    "",
    ...(data.verification
      ? [
          `- **Result:** ${data.verification.result}`,
          `- **Samples:** ${data.verification.sample_count}`,
          `- **Completed:** ${timestamp(data.verification.completed_at)}`,
          "",
          "```json",
          json({ affected: data.verification.affected, preservation: data.verification.preservation }),
          "```",
        ]
      : ["No verification record is attached yet."]),
    "",
    "## 7. Recovery",
    "",
    ...(recovery
      ? [
          `- **Recovery run:** ${recovery.id}`,
          `- **Status:** ${recovery.status}`,
          `- **Current stage:** ${recovery.current_stage}`,
          `- **Last verified stage:** ${recovery.last_verified_stage}`,
          `- **Retries:** ${recovery.retry_count}/${recovery.maximum_retries}`,
          "",
          "| Stage | Status | Requested weight | Observed weight | Samples / required | Started | Verified |",
          "| --- | --- | ---: | ---: | ---: | --- | --- |",
          ...recovery.stages.map((stage) => `| ${stage.name} | ${stage.status} | ${stage.requested_weight ?? "probe"} | ${stage.observed_weight ?? "—"} | ${stage.sample_count}/${stage.minimum_samples} | ${timestamp(stage.started_at)} | ${timestamp(stage.verified_at)} |`),
          "",
          "### Stage evidence",
          "",
          "```json",
          json(recovery.stages.map((stage) => ({ stage: stage.name, result: stage.result }))),
          "```",
        ]
      : action?.kind === "INSTANCE_QUARANTINE"
        ? [
            "Instance recovery uses a direct-probe gate rather than a staged ReintegrationRun.",
            `- **Verification:** ${data.verification?.result ?? "Not recorded"}`,
            `- **Probe gate:** ${json(data.verification?.affected)}`,
            `- **Restore confirmation:** ${json(action.attempts.filter((attempt) => attempt.operation === "restore_instance_after_probe_gate").map((attempt) => ({ status: attempt.status, observed_state: attempt.observed_state })))}`,
          ]
        : data.recovery
          ? [`A staged recovery run exists (${data.recovery.id}), but its detailed stages were not available for this export.`]
          : ["No recovery run is recorded; no membership recovery may have been required for this decision."]),
    "",
    "## 8. Event timeline",
    "",
    ...(events.length ? events.map((event) => `- ${timestamp(event.at)} — ${event.label}`) : ["No timestamped events were available."]),
    "",
    "## 9. Limitations and provenance",
    "",
    "- This report is assembled from the persisted Decision Trace, fault, action, verification, and recovery records available at generation time.",
    "- Missing records are labeled as not recorded; they are not inferred or filled with simulated values.",
    "- The report is a point-in-time export and does not update when incident state changes.",
    `- **Observation window ID:** ${data.evidence?.window_id ?? "Not recorded"}`,
    `- **Fingerprint ID/hash:** ${data.fingerprint?.id ?? "Not recorded"} / ${data.fingerprint?.hash ?? "Not recorded"}`,
    `- **Certificate ID/hash:** ${data.certificate?.id ?? "Not recorded"} / ${data.certificate?.hash ?? "Not recorded"}`,
    `- **Action ID:** ${action?.id ?? "Not recorded"}`,
    `- **Recovery ID:** ${recovery?.id ?? data.recovery?.id ?? "Not recorded"}`,
    "",
  ];

  return {
    outcome,
    filename: `incident-analysis-${data.incident.id.slice(0, 8)}.md`,
    content: lines.join("\n"),
  };
}
