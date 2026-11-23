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

test('Gold connection and foundation schemas are discoverable without Use Cases settings', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Connection settings', exact: true }).click();
  const dialog=page.getByRole('dialog', { name: 'Live data connection' });
  await expect(dialog).toBeVisible();
  await expect(page.getByLabel('Gold catalog', { exact: true })).toHaveValue('media-poc');
  await expect(page.getByLabel('Gold schema', { exact: true })).toHaveValue('gold');
  await expect(page.getByLabel('Use Cases catalog', { exact: true })).toHaveCount(0);
  await expect(dialog).toContainText('directly from published Gold');
  await expect(page.getByRole('button', { name: 'Verify & connect' })).toBeDisabled();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation').getByRole('button', { name: 'Gold Data Explorer' }).click();
  await expect(page.getByRole('button', { name: /Use case tables/ })).toHaveCount(0);
  await page.getByRole('button', { name: 'All schemas', exact: true }).click();
  await expect(page.locator('.schema-browser-controls')).toContainText('377 tables');
  await page.getByLabel('Schema location').selectOption('media-poc.silver');
  await expect(page.locator('.schema-browser-controls')).toContainText('91 tables');
  await page.getByLabel('Search tables or columns').fill('spend');
  await expect(page.locator('.schema-table')).toBeVisible();
  await page.screenshot({ path: 'artifacts/all-schema-explorer.png', fullPage: true });
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

test('campaign names and platform filters preserve Gold identity and explain unsupported grains', async ({ page }) => {
  await page.goto('/');
  const campaign=page.getByLabel('Campaign', { exact: true });
  await expect(campaign.locator('option[value="CMP001"]')).toHaveText('Everyday Checking - Regional Acquisition');
  await expect(campaign.locator('option[value="CMP006"]')).toHaveText('Small Business Banking Growth');
  await campaign.selectOption('CMP001');
  await page.getByLabel('Platform', { exact: true }).selectOption('meta');
  await expect(page.locator('.metric-card').nth(2)).toContainText('Unavailable for this selection');
  await page.getByRole('button', { name: 'Details for Funded accounts' }).click();
  await expect(page.getByRole('dialog')).toContainText('published Gold grain');
  await page.keyboard.press('Escape');
  await expect(page.locator('.chart-empty').last()).toContainText('campaign');
  await page.screenshot({ path: 'artifacts/gold-campaign-platform-filters.png', fullPage: true });
  const response=await page.request.get('/api/dashboard/overview?campaign=CMP001&platform=meta');
  const data=await response.json();
  expect(data.metrics.every((m: {source: string}) => m.source.startsWith('media-poc.gold.'))).toBe(true);
  expect(data.metrics[2].value).toBeNull();
  await page.getByRole('button', { name: 'Reset', exact: true }).click();
  await expect(page.locator('.metric-value').nth(2)).toHaveText('282');
});

test('shared app access is explicit and the configured namespace is read-only', async ({ page }) => {
  await page.route('**/api/bootstrap',async route => {
    const response=await route.fetch();const body=await response.json();
    await route.fulfill({json:{...body,mode:'live',sql_auth_mode:'app',shared_data:true,
      catalog:'source-data',schema:'app_gold',analytics_catalog:'source-data',analytics_schema:'app_gold'}});
  });
  await page.route('**/api/connection',async route => {
    await route.fulfill({json:{mode:'live',sql_auth_mode:'app',shared_data:true,connection:{
      source_mode:'gold',gold_catalog:'source-data',gold_schema:'app_gold',use_cases_catalog:'',use_cases_schema:''}}});
  });
  await page.goto('/');
  await expect(page.locator('.workspace-identity')).toContainText('Shared app identity');
  await expect(page.locator('.population-note').first()).toContainText('Shared app dataset');
  await page.getByRole('button',{name:'Connection settings',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Live data connection'});
  await expect(dialog).toContainText('Shared app access');
  await expect(page.getByLabel('Gold catalog',{exact:true})).toHaveValue('source-data');
  await expect(page.getByLabel('Gold catalog',{exact:true})).toHaveAttribute('readonly','');
  await expect(page.getByLabel('Gold schema',{exact:true})).toHaveValue('app_gold');
  await expect(page.getByLabel('Gold schema',{exact:true})).toHaveAttribute('readonly','');
  await expect(page.getByRole('button',{name:'Verify & connect',exact:true})).toBeEnabled();
  await page.screenshot({path:'artifacts/app-identity-connection.png',fullPage:false});
});

test('More filters bind product, market, currency and plan values to the reports', async ({ page }) => {
  const choices=await (await page.request.get('/api/bootstrap')).json();
  const source=await (await page.request.get('/api/table/mart_banking_funded_accounts_monthly?size=1')).json();
  const record=source.rows[0];
  await page.goto('/');
  await expect(page.locator('.metric-value').nth(2)).toHaveText('282');
  await page.getByRole('button',{name:'More filters'}).click();
  await expect(page.getByRole('group',{name:'Additional report filters'})).toBeVisible();
  await page.getByLabel('Product',{exact:true}).selectOption(String(record.product_id));
  await page.getByLabel('Market',{exact:true}).selectOption(String(record.market_id));
  await page.getByLabel('Currency',{exact:true}).selectOption('USD');
  const params=new URLSearchParams({product:String(record.product_id),market:String(record.market_id),currency:'USD'});
  const expected=await (await page.request.get('/api/dashboard/overview?'+params)).json();
  await expect(page.locator('.metric-value').nth(2)).toHaveText(String(expected.metrics[2].value));
  await expect(page.locator('.metric-card').first()).toContainText('Unavailable for this selection');
  const request=page.waitForRequest(req=>new URL(req.url()).pathname.startsWith('/api/dashboard/') && new URL(req.url()).searchParams.get('plan')===choices.plans[0]);
  await page.getByLabel('Plan version',{exact:true}).selectOption(choices.plans[0]);
  await request;
  await expect(page.getByLabel('Plan version',{exact:true})).toHaveValue(choices.plans[0]);
  await page.getByRole('button',{name:'Reset',exact:true}).click();
  await expect(page.locator('.metric-value').nth(2)).toHaveText('282');
  await expect(page.getByLabel('Plan version',{exact:true})).toHaveValue('');
  await page.screenshot({path:'artifacts/advanced-filters.png',fullPage:false});
});

test('failed choices are explained without blank currency or plan controls and Refresh data reloads them', async ({ page }) => {
  let loads=0;
  await page.route('**/api/bootstrap',async route=>{
    const response=await route.fetch();const body=await response.json();loads++;
    if(loads===1){
      for(const key of ['platforms','products','markets','currencies','plans']){
        body[key]=[];
        body.filter_status[key]={state:'unavailable',message:'Choices could not be loaded. Refresh data to retry.',sources:[],errors:['Test option failure']};
      }
    }
    await route.fulfill({json:body});
  });
  await page.goto('/');
  await expect(page.getByLabel('Platform',{exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'More filters'}).click();
  for(const label of ['Product','Market','Currency','Plan version'])await expect(page.getByLabel(label,{exact:true})).toBeDisabled();
  await expect(page.getByLabel('Currency',{exact:true}).locator('option:checked')).toHaveText('USD (not loaded)');
  await expect(page.getByLabel('Plan version',{exact:true}).locator('option:checked')).toHaveText('Default plan');
  await page.getByRole('button',{name:'Refresh data',exact:true}).click();
  await expect(page.getByLabel('Platform',{exact:true})).toBeEnabled();
  for(const label of ['Product','Market','Currency','Plan version'])await expect(page.getByLabel(label,{exact:true})).toBeEnabled();
  expect(loads).toBeGreaterThan(1);
  await page.getByLabel('Platform',{exact:true}).selectOption('meta');
  await expect(page.locator('.metric-value').first()).not.toHaveText('$790.2K');
});

test('foundation refresh errors preserve the selected filters and usable prior choices', async ({ page }) => {
  let loads=0;
  await page.route('**/api/bootstrap',async route=>{
    loads++;
    if(loads>1)await route.fulfill({status:503,json:{detail:'Simulated metadata refresh failure'}});
    else await route.continue();
  });
  await page.goto('/');
  await page.getByLabel('Platform',{exact:true}).selectOption('meta');
  await expect(page.locator('.metric-value').first()).not.toHaveText('$790.2K');
  await page.getByRole('button',{name:'Refresh data',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Showing the last loaded options');
  await expect(page.getByLabel('Platform',{exact:true})).toHaveValue('meta');
  await expect(page.getByLabel('Platform',{exact:true})).toBeEnabled();
  await expect(page.getByRole('heading',{name:'Executive overview',exact:true})).toBeVisible();
});

test('a reporting currency absent from available choices never renders as a blank selection', async ({ page }) => {
  await page.route('**/api/bootstrap',async route=>{
    const response=await route.fetch();const body=await response.json();
    await route.fulfill({json:{...body,currencies:['EUR']}});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'More filters'}).click();
  await expect(page.getByLabel('Currency',{exact:true})).toHaveValue('EUR');
  await expect(page.getByLabel('Currency',{exact:true}).locator('option:checked')).toHaveText('EUR');
});

test('Genie shared app mode presents private chat without viewer scope setup', async ({ page }) => {
  await page.route('**/api/genie/config',async route=>route.fulfill({json:{mode:'live',configured:true,space_id:'space-1',
    auth_mode:'app',shared_data:true,examples:['Show spend by platform']}}));
  await page.route('**/api/genie/messages',async route=>route.fulfill({json:{status:'COMPLETED',conversation_id:'conv-1',
    message_id:'msg-1',conversation_key:'test-key',text:'Browser test response',queries:[]}}));
  await page.goto('/');
  await page.getByRole('navigation').getByRole('button',{name:'Ask Genie'}).click();
  await expect(page.locator('.genie-panel')).toContainText('Conversations are isolated');
  await page.getByRole('button',{name:'Show spend by platform',exact:true}).click();
  await expect(page.locator('.genie-answer')).toContainText('Browser test response');
  await expect(page.locator('.inline-error')).toHaveCount(0);
});

test('reference-inspired campaign scorecard presents names, business columns and cost context', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Campaign effectiveness',exact:true})).toBeVisible();
  const report=page.locator('.compact-table');
  await expect(report.locator('.report-context')).toContainText('Synthetic campaign cohorts');
  await expect(report.locator('.report-grain')).toHaveText('Campaign / platform cohort');
  await expect(report.locator('thead')).toContainText('Platform spend (USD)');
  await expect(report.locator('.campaign-cell').first()).toBeVisible();
  await expect(report.locator('.campaign-cell').first()).not.toHaveText(/^CMP\d+$/);
  await expect(report.locator('thead')).not.toContainText('Campaign Match Token');
  await report.getByRole('button',{name:'All columns',exact:true}).click();
  await expect(report.locator('thead')).toContainText('Campaign Match Token');
  await report.getByRole('button',{name:'Report columns',exact:true}).click();
  await expect(report.locator('thead')).not.toContainText('Campaign Match Token');
  await page.screenshot({path:'artifacts/campaign-effectiveness-scorecard.png',fullPage:true});
});
