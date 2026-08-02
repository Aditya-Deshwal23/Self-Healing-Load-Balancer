import axe from "axe-core";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PageHeader, Panel, StateMessage, StatusTag } from "@/components/ui";

describe("critical feedback primitives", () => {
  it("render labels and pass an automated accessibility scan", async () => {
    const { container, getByRole, getByText } = render(
      <main>
        <PageHeader
          eyebrow="Incident"
          title="Checkout on B"
          brief="One route membership is failing."
        />
        <Panel title="Observed state" id="observed-state">
          <StatusTag tone="warning">VERIFYING</StatusTag>
          <StateMessage state="unknown" title="Waiting for samples">
            Zero samples cannot confirm success.
          </StateMessage>
        </Panel>
      </main>,
    );

    expect(
      getByRole("heading", { level: 1, name: "Checkout on B" }),
    ).toBeVisible();
    expect(getByText("VERIFYING")).toBeVisible();
    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });
});
