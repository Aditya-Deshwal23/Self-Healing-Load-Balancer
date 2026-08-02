import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";

test("Researcher reaches the real healthy Command Center", async ({
  page,
}, testInfo) => {
  const password = readFileSync(
    resolve("..", ".secrets", "bootstrap_password"),
    "utf8",
  ).trim();
  await page.goto("/login");
  await page.getByLabel("Email").fill("researcher@shlb.local");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    /Traffic is healthy|fails|Evidence is/,
  );
  await expect(
    page
      .getByRole("navigation", { name: "Primary navigation" })
      .getByRole("link"),
  ).toHaveCount(testInfo.project.name === "mobile-read-only" ? 2 : 7);
  await expect(page.getByText("Simulated data.")).toHaveCount(0);
  if (testInfo.project.name === "mobile-read-only") {
    await expect(page.getByText(/Telemetry live · SSE/)).toBeHidden();
  } else {
    await expect(page.getByText(/Telemetry live · SSE/)).toBeVisible();
  }
});

test("route matrix exposes desired and observed state without horizontal page overflow", async ({
  page,
}) => {
  test.skip(
    page.viewportSize()?.width === 390,
    "The mobile critical surface intentionally prioritizes incident read-only state.",
  );
  const password = readFileSync(
    resolve("..", ".secrets", "bootstrap_password"),
    "utf8",
  ).trim();
  await page.goto("/login");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.goto("/app/traffic/matrix");
  await expect(
    page.getByRole("table", { name: /Live route by instance/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: /checkout on inst-b/i }).click();
  await expect(
    page.getByRole("dialog", { name: /checkout.*inst-b/i }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
});
