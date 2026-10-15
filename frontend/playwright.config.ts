import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  use: {
    baseURL: "http://127.0.0.1:5175",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "venv/bin/python -m uvicorn main:app --app-dir backend/src --host 127.0.0.1 --port 8011",
      cwd: "..",
      url: "http://127.0.0.1:8011/openapi.json",
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5175 --strictPort",
      url: "http://127.0.0.1:5175",
      env: { VITE_BACKEND_API_PATH: "/api/", VITE_PROXY_TARGET: "http://127.0.0.1:8011" },
    },
  ],
});
