import { test, expect } from '@playwright/test';

test('CAO route loads canned brief and shows decision toast on Accept', async ({ page }) => {
  await page.goto('/cao/RLS-25-067');
  await expect(page.locator('cao-view')).toBeVisible();

  await expect(page.locator('cao-view').getByText(/Brief for CAO Review/)).toBeVisible({ timeout: 5000 });

  await page.locator('cao-view button.accept').click();

  await expect(page.locator('cao-view').getByText(/v0\.2\.1/)).toBeVisible();
});
