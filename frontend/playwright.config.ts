/**
 * Browser end-to-end tests (e2e/*.spec.ts). Run through the runner, which builds the SPA and starts a server on a
 * throwaway database loaded with the demo data:   ../../for_testing --e2e
 * By hand against a running server:                E2E_BASE_URL=http://127.0.0.1:8000 npx playwright test
 * (the tests change data: use a disposable database, e.g. the one --e2e creates).
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e-results", // traces and screenshots of failed tests
  fullyParallel: false,
  workers: 1, // one shared database
  retries: 0,
  timeout: 30_000,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:8765",
    locale: "en-US",
    timezoneId: "America/Mexico_City",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } }],
});
