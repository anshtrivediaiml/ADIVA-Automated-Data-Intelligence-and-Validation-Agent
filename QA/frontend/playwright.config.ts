import { defineConfig } from "@playwright/test";

const baseURL = process.env.QA_FRONTEND_URL ?? "http://127.0.0.1:5173";

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  reporter: [["list"], ["html", { outputFolder: "../reports/playwright-report" }]],
});
