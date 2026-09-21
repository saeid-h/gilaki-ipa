import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://127.0.0.1:4173",
    locale: "en-US",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "cd ../api && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 18741",
      port: 18741,
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: "python3 -m http.server 4173 --bind 127.0.0.1",
      port: 4173,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
