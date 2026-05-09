import { test, expect } from '@playwright/test';

test('requester full journey: intake → form → status → cure → submit-disabled', async ({ page }) => {
  await page.goto('/static/index.html');
  await expect(page.locator('rls-shell')).toBeVisible();

  const intake = page.locator('intake-panel');
  await expect(intake).toBeVisible();
  const ta = intake.locator('textarea');
  await ta.fill('Need legal review on a permit denial for parcel 12345.');
  await intake.locator('button.primary').click();

  await expect(page.locator('form-panel')).toBeVisible();

  const titleInput = page.locator('form-panel input[data-field=title]');
  await titleInput.fill('Permit denial parcel 12345');
  await titleInput.blur();

  await page.waitForTimeout(1200);

  await page.locator('form-panel button.primary').click();
  await expect(page.locator('status-panel')).toBeVisible();

  await page.locator('step-bar button.step:has-text("Submit")').click();
  const submitBtn = page.locator('submit-panel button.submit');
  await expect(submitBtn).toBeDisabled();

  await expect(page.locator('submit-panel pre')).toBeVisible();
});
