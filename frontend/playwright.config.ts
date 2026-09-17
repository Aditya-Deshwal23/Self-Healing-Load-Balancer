import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "../.artifacts/playwright",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.SHLB_E2E_URL ?? "https://localhost:8443",
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: "mobile-read-only",
      use: { ...devices["iPhone 13"], viewport: { width: 390, height: 844 } },
    },
  ],
});
