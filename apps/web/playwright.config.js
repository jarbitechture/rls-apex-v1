import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: 'list',
  use: {
    // Port 8090 — 8080 conflicts with Docker Desktop on the dev workstation.
    baseURL: 'http://127.0.0.1:8090',
    trace: 'on-first-retry',
    headless: true,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'cd ../.. && DEV_AUTH_BYPASS=1 .venv/bin/python -m uvicorn apps.gateway.main:app --host 127.0.0.1 --port 8090',
    url: 'http://127.0.0.1:8090/static/index.html',
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
