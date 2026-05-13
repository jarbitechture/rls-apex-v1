import { test, expect } from '@playwright/test';

// LOAD-BEARING: Asserts [data-testid="rls-disclaimer-banner"] is present in the rendered DOM.
// Per the compliance comment in rls-disclaimer-banner.js, a future frontend cutover MUST keep
// this assertion intact and the testid in place. Do not weaken to a text-match.

test('legal disclaimer banner is present on the requester surface', async ({ page }) => {
  await page.goto('/static/index.html');
  await expect(page.locator('rls-shell')).toBeVisible();
  const banner = page.locator('[data-testid="rls-disclaimer-banner"]');
  await expect(banner).toBeVisible();
});

test('disclaimer banner renders validator-framed copy (does not provide legal advice)', async ({ page }) => {
  await page.goto('/static/index.html');
  const banner = page.locator('[data-testid="rls-disclaimer-banner"]');
  await expect(banner).toContainText(/Grades a request-for-legal-services draft/);
  await expect(banner).toContainText(/Does not provide legal advice/);
  await expect(banner).toContainText(/Does not cite case law/);
});
