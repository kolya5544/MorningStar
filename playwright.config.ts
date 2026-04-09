import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "python server/run_test_server.py",
      url: "http://127.0.0.1:8000/api/health",
      timeout: 120000,
      reuseExistingServer: true,
    },
    {
      command: "cmd /c npm run dev -- --host 127.0.0.1 --port 4173",
      url: "http://127.0.0.1:4173",
      timeout: 120000,
      reuseExistingServer: true,
    },
  ],
});

