import { describe, expect, it } from "vitest";
import { actionSemantics, membershipSemantics } from "@/lib/status";

describe("status semantics", () => {
  it("uses verified green only for confirmed healthy/effective outcomes", () => {
    expect(membershipSemantics.healthy.tone).toBe("success");
    expect(actionSemantics.COMMITTED.tone).toBe("success");
    expect(membershipSemantics.verifying.tone).toBe("warning");
    expect(actionSemantics.APPLIED.tone).toBe("warning");
    expect(actionSemantics.RESULT_UNKNOWN.tone).toBe("danger");
  });

  it("always pairs a machine state with a human label", () => {
    for (const semantic of [
      ...Object.values(membershipSemantics),
      ...Object.values(actionSemantics),
    ]) {
      expect(semantic.label.length).toBeGreaterThan(0);
      expect(semantic.tone.length).toBeGreaterThan(0);
    }
  });
});
