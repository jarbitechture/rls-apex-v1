import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8080',
    trace: 'on-first-retry',
    headless: true,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'cd ../.. && DEV_AUTH_BYPASS=1 .venv/bin/python -m uvicorn apps.gateway.main:app --host 127.0.0.1 --port 8080',
    url: 'http://127.0.0.1:8080/static/index.html',
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
