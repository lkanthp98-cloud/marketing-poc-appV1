import { test, expect } from '@playwright/test';

test('executive dashboard renders, definitions open, and all business pages work', async ({ page }) => {
  const failures: string[] = [];
  page.on('pageerror', error => failures.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Executive overview', exact: true })).toBeVisible();
  await expect(page.locator('.metric-value').first()).toHaveText('$790.2K');
  await expect(page.locator('.chart-canvas')).toHaveCount(3);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'artifacts/executive-overview.png', fullPage: true });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'artifacts/desktop-preview.png', fullPage: false });
  await page.getByRole('button', { name: 'Details for Media investment' }).click();
  await expect(page.getByRole('dialog')).toContainText('Native vendor delivery cost');
  await page.keyboard.press('Escape');
  for (const title of ['Campaign & Paid Media', 'Customer Acquisition', 'Digital & Offline', 'Financial Performance', 'Experiments & Brand']) {
    await page.getByRole('navigation').getByRole('button', { name: title }).click();
    await expect(page.locator('.metric-card')).toHaveCount(4);
    await expect(page.locator('.chart-canvas')).toHaveCount(3);
    await expect(page.locator('.error-card')).toHaveCount(0);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'artifacts/experiments-brand.png', fullPage: true });
  expect(failures).toEqual([]);
});

test('platform and date filters update actual data and saved view restores filters', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.metric-value').first()).toHaveText('$790.2K');
  await page.getByLabel('Platform', { exact: true }).selectOption('google_ads');
  await expect(page.locator('.metric-value').first()).not.toHaveText('$790.2K');
  const filtered = await page.locator('.metric-value').first().innerText();
  await page.getByRole('button', { name: 'More filters' }).click();
  await page.getByRole('button', { name: 'Save view', exact: true }).click();
  await page.getByRole('button', { name: 'Reset', exact: true }).click();
  await expect(page.locator('.metric-value').first()).toHaveText('$790.2K');
  await page.getByRole('button', { name: 'Saved view', exact: true }).click();
  await expect(page.getByLabel('Platform', { exact: true })).toHaveValue('google_ads');
  await expect(page.locator('.metric-value').first()).toHaveText(filtered);
  await page.getByLabel('Start date').fill('2026-11-01');
  await expect(page.locator('.metric-value').first()).toHaveText('—');
  await expect(page.locator('.chart-empty').first()).toBeVisible();
});

test('Gold explorer supports table discovery, schema, lineage, dictionary and export', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('navigation').getByRole('button', { name: 'Gold Data Explorer' }).click();
  await expect(page.locator('.explorer-summary')).toContainText('113');
  await page.getByLabel('Search Gold tables').fill('mart_vendor_media_daily');
  await expect(page.locator('.catalog-item')).toHaveCount(1);
  await page.locator('.catalog-item').click();
  await expect(page.locator('.table-scroll tbody tr')).toHaveCount(20);
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(page.locator('.pagination')).toContainText('Page 2');
  await page.getByRole('button', { name: 'Schema', exact: true }).click();
  await expect(page.locator('.schema-table')).toContainText('spend_amount');
  await page.getByRole('button', { name: 'Lineage', exact: true }).click();
  await expect(page.locator('.lineage-row').first()).toBeVisible();
  await page.getByRole('button', { name: 'KPI dictionary', exact: true }).click();
  await expect(page.locator('.definition-item').first()).toBeVisible();
  await page.getByRole('button', { name: 'Data', exact: true }).click();
  await page.getByLabel('Search table records').fill('youtube');
  await expect(page.locator('.table-scroll tbody tr').first()).toContainText('youtube');
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Export CSV' }).click();
  expect((await download).suggestedFilename()).toBe('mart_vendor_media_daily-filtered.csv');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'artifacts/gold-explorer.png', fullPage: true });
});

test('mobile layout has usable navigation and no page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.locator('.metric-card')).toHaveCount(4);
  await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
  await page.getByRole('navigation').getByRole('button', { name: 'Customer Acquisition' }).click();
  await expect(page.getByRole('heading', { name: 'Customer Acquisition', exact: true })).toBeVisible();
  await expect(page.locator('.chart-canvas')).toHaveCount(3);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'artifacts/mobile-acquisition.png', fullPage: true });
});

test('Use Cases data, all uploaded schemas and connection settings are discoverable', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: 'Connection settings', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Live data connection' })).toBeVisible();
  await expect(page.getByLabel('Use Cases catalog', { exact: true })).toHaveValue('source-data');
  await expect(page.getByLabel('Use Cases schema', { exact: true })).toHaveValue('usecases');
  await page.getByLabel('Data sources', { exact: true }).selectOption('gold');
  await expect(page.getByLabel('Gold catalog', { exact: true })).toBeEnabled();
  await expect(page.getByLabel('Use Cases catalog', { exact: true })).toBeDisabled();
  await page.getByLabel('Data sources', { exact: true }).selectOption('use_cases');
  await expect(page.getByLabel('Gold catalog', { exact: true })).toBeDisabled();
  await expect(page.getByLabel('Use Cases catalog', { exact: true })).toBeEnabled();
  await page.getByLabel('Data sources', { exact: true }).selectOption('both');
  await expect(page.getByRole('button', { name: 'Verify & connect' })).toBeDisabled();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation').getByRole('button', { name: 'Gold Data Explorer' }).click();
  await page.getByRole('button', { name: /Use case tables/ }).click();
  await expect(page.locator('.explorer-summary')).toContainText('30');
  await page.getByLabel('Search Use Case tables').fill('uc02_vendor_media_daily');
  await page.locator('.catalog-item').click();
  await page.getByRole('button', { name: 'Schema', exact: true }).click();
  await expect(page.locator('.schema-table')).toContainText('_uc_publication_id');
  await expect(page.locator('.entity-heading')).toContainText('source-data / usecases');
  await page.screenshot({ path: 'artifacts/use-cases-explorer.png', fullPage: true });
  await page.getByRole('button', { name: 'All schemas', exact: true }).click();
  await expect(page.locator('.schema-browser-controls')).toContainText('407 tables');
  await page.getByLabel('Schema location').selectOption('media-poc.silver');
  await expect(page.locator('.schema-browser-controls')).toContainText('91 tables');
  await page.getByLabel('Search tables or columns').fill('spend');
  await expect(page.locator('.schema-table')).toBeVisible();
  await page.screenshot({ path: 'artifacts/all-schema-explorer.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('Genie tab answers guided sample questions with SQL and results', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('navigation').getByRole('button', { name: 'Ask Genie' }).click();
  await expect(page.getByRole('heading', { name: 'Ask your marketing data' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Report filters' })).toBeHidden();
  await page.getByRole('button', { name: 'Show marketing spend by platform in USD', exact: true }).click();
  await expect(page.locator('.genie-answer')).toContainText('not generated by live Genie');
  await expect(page.locator('.genie-answer table tbody tr').first()).toBeVisible();
  await page.getByText('View generated SQL').click();
  await expect(page.locator('.genie-answer pre')).toContainText('SUM(spend_amount)');
  await page.screenshot({ path: 'artifacts/genie-analytics.png', fullPage: true });
  await page.getByRole('navigation').getByRole('button', { name: 'Executive Overview' }).click();
  await page.getByRole('navigation').getByRole('button', { name: 'Ask Genie' }).click();
  await expect(page.locator('.genie-answer')).toBeVisible();
  await page.getByRole('button', { name: 'New conversation' }).click();
  await expect(page.locator('.genie-answer')).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('single-source deployments load dashboards and disable the other explorer layer', async ({ page }) => {
  test.skip(!process.env.SOURCE_MODE_GOLD_URL || !process.env.SOURCE_MODE_UC_URL, 'Start Gold-only and Use-Cases-only sample servers to run this check.');
  for (const [url, inactive, prefix] of [
    [process.env.SOURCE_MODE_GOLD_URL!, /Use case tables/, 'media-poc.gold.'],
    [process.env.SOURCE_MODE_UC_URL!, /Gold tables/, 'source-data.usecases.'],
  ] as const) {
    await page.goto(url);
    await expect(page.locator('.metric-card')).toHaveCount(4);
    await expect(page.locator('.table-source')).toContainText(prefix);
    for (const title of ['Campaign & Paid Media', 'Customer Acquisition', 'Digital & Offline', 'Financial Performance', 'Experiments & Brand']) {
      await page.getByRole('navigation').getByRole('button', { name: title }).click();
      await expect(page.locator('.chart-canvas')).toHaveCount(3);
      await expect(page.locator('.error-card')).toHaveCount(0);
      await expect(page.locator('.table-source')).toContainText(prefix);
    }
    await page.getByRole('navigation').getByRole('button', { name: 'Gold Data Explorer' }).click();
    await expect(page.getByRole('button', { name: inactive })).toBeDisabled();
    await page.getByRole('button', { name: 'Schema', exact: true }).click();
    await expect(page.locator('.schema-table tbody tr').first()).toBeVisible();
  }
});
