const { test, expect, chromium } = require('@playwright/test');

test.describe('Portal Public UI E2E Tests', () => {
  let browser;
  let context;
  let page;

  test.beforeAll(async () => {
    // Nix-built Chromium
    browser = await chromium.launch({
      executablePath: process.env.CHROMIUM_PATH || '/nix/store/9fjg59mab9j8c5r61dx2k5gcbd2f5mpm-chromium-148.0.7778.96/bin/chromium',
      headless: true
    });

    // Compile settings so obtainium-export.json has the seed apps
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.request.post('http://localhost:8000/api/apps/compile');
    await context.close();
  });

  test.afterAll(async () => {
    if (browser) {
      await browser.close();
    }
  });

  test.beforeEach(async () => {
    context = await browser.newContext({
      baseURL: 'http://localhost:8000'
    });
    page = await context.newPage();
    
    // Capture logs/errors
    page.on('pageerror', exception => {
      console.log(`[BROWSER EXCEPTION] ${exception.stack || exception}`);
    });
    page.on('console', msg => {
      console.log(`[BROWSER LOG] [${msg.type()}] ${msg.text()}`);
    });

    // Navigate to root (portal view)
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('#apps-table-body');
    // Wait for the loading spinner to disappear to ensure API fetch and DOM rendering are complete
    await expect(page.locator('.loading-state')).not.toBeVisible();
  });

  test.afterEach(async () => {
    if (context) {
      await context.close();
    }
  });

  test('1. Portal initial layout check', async () => {
    // Check navigation buttons
    await expect(page.locator('#nav-portal')).toBeVisible();
    await expect(page.locator('#nav-dashboard')).toBeVisible();

    // Check main title
    await expect(page.locator('h1:has-text("Android 端末のプロビジョニングを快適に")')).toBeVisible();

    // Check search and filter controls
    await expect(page.locator('#app-search-input')).toBeVisible();
    await expect(page.locator('#portal-category-filter')).toBeVisible();

    // Check apps table
    await expect(page.locator('#portal-view .apps-table')).toBeVisible();
  });

  test('2. Navigation routing to dashboard and back', async () => {
    // Click dashboard link
    const navDashboard = page.locator('#nav-dashboard');
    await navDashboard.click();
    await expect(page).toHaveURL(/#\/dashboard/);
    await expect(page.locator('#dashboard-view')).toBeVisible();
    await expect(page.locator('#portal-view')).not.toBeVisible();

    // Click portal link
    const navPortal = page.locator('#nav-portal');
    await navPortal.click();
    await expect(page).toHaveURL(/#\/|#$/);
    await expect(page.locator('#portal-view')).toBeVisible();
    await expect(page.locator('#dashboard-view')).not.toBeVisible();
  });

  test('3. Search apps in portal list', async () => {
    const searchInput = page.locator('#app-search-input');
    
    // Type App2 to find App2 app
    await searchInput.fill('app2');
    const tableBody = page.locator('#apps-table-body');
    await expect(tableBody.locator('tr:has-text("App2")').first()).toBeVisible();

    // Type a non-existent app name
    await searchInput.fill('nonexistent-app-xyz');
    await expect(tableBody.locator('tr.empty-row')).toBeVisible();
    await expect(tableBody).toContainText('該当するアプリが見つかりません。');
  });

  test('4. Category filtering in portal list', async () => {
    const filterSelect = page.locator('#portal-category-filter');
    
    // Choose Game category (if it exists)
    const options = await filterSelect.locator('option').allTextContents();
    if (options.includes('Game')) {
      await filterSelect.selectOption('Game');
      const tableRows = await page.locator('#apps-table-body tr.app-row').all();
      for (const row of tableRows) {
        await expect(row.locator('.category-tags')).toContainText('Game');
      }
    }
  });

  test('5. Category sorting in portal list', async () => {
    const sortHeader = page.locator('#portal-sort-category');
    const sortIcon = page.locator('#portal-sort-icon');

    // Initial state is "↕"
    await expect(sortIcon).toHaveText('↕');

    // First click: Ascending "▲"
    await sortHeader.click();
    await expect(sortIcon).toHaveText('▲');

    // Second click: Descending "▼"
    await sortHeader.click();
    await expect(sortIcon).toHaveText('▼');

    // Third click: Normal "↕"
    await sortHeader.click();
    await expect(sortIcon).toHaveText('↕');
  });

  test('6. Copy obtainium export URL', async () => {
    const copyBtn = page.locator('#copy-export-url-btn');
    const toast = page.locator('#copy-toast');

    await expect(toast).toHaveClass(/hidden/);
    await copyBtn.click();
    await expect(toast).not.toHaveClass(/hidden/);
    await expect(toast).toHaveText('コピーしました！');
  });
});
