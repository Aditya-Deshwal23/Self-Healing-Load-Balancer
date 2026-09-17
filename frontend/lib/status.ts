import type { ActionLifecycle, MembershipState } from "@/lib/types";
import type { Tone } from "@/components/ui";

export const membershipSemantics: Record<MembershipState, { label: string; tone: Tone }> = {
  healthy: { label: "Healthy", tone: "success" },
  degraded: { label: "Degraded", tone: "warning" },
  failing: { label: "Failing", tone: "danger" },
  quarantined: { label: "Quarantined", tone: "danger" },
  verifying: { label: "Verifying", tone: "warning" },
  reintegrating: { label: "Reintegrating", tone: "info" },
  unknown: { label: "Unknown", tone: "neutral" },
  "no-membership": { label: "No membership", tone: "muted" },
};

export const actionSemantics: Record<ActionLifecycle, { label: string; tone: Tone }> = {
  PLANNED: { label: "Planned", tone: "neutral" },
  SAFETY_CHECKED: { label: "Safety checked", tone: "neutral" },
  PREPARED: { label: "Prepared", tone: "warning" },
  APPLIED: { label: "Applied · awaiting readback", tone: "warning" },
  STATE_CONFIRMED: { label: "State confirmed", tone: "info" },
  VERIFYING: { label: "Verifying", tone: "warning" },
  COMMITTED: { label: "Effective", tone: "success" },
  ROLLING_BACK: { label: "Rolling back", tone: "warning" },
  ROLLED_BACK: { label: "Rolled back", tone: "neutral" },
  NEEDS_REVIEW: { label: "Needs review", tone: "danger" },
  RESULT_UNKNOWN: { label: "Result unknown", tone: "danger" },
  EXPIRED: { label: "Expired", tone: "muted" },
  SUPERSEDED: { label: "Superseded", tone: "muted" },
};
