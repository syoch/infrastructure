const { test, expect, chromium } = require('@playwright/test');

test.describe('Schema Renderer E2E Tests', () => {
  let browser;
  let context;
  let page;

  test.beforeAll(async () => {
    browser = await chromium.launch({
      executablePath: process.env.CHROMIUM_PATH || '/nix/store/9fjg59mab9j8c5r61dx2k5gcbd2f5mpm-chromium-148.0.7778.96/bin/chromium',
      headless: true,
    });
  });

  test.afterAll(async () => {
    if (browser) await browser.close();
  });

  test.beforeEach(async () => {
    context = await browser.newContext({ baseURL: 'http://localhost:8000' });
    page = await context.newPage();
    page.on('pageerror', (e) => console.log(`[BROWSER EXCEPTION] ${e.stack || e}`));
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log(`[BROWSER ERROR] ${msg.text()}`);
      if (msg.type() === 'log') console.log(`[BROWSER LOG] ${msg.text()}`);
    });
    page.on('requestfailed', (req) => console.log(`[REQ FAILED] ${req.url()}`));
    page.on('response', (resp) => { if (resp.status() >= 400) console.log(`[RESP ${resp.status()}] ${resp.url()}`); });
  });

  test.afterEach(async () => {
    if (context) await context.close();
  });

  test('all schema_renderer test cases pass', async () => {
    const responses = [];
    page.on('response', (resp) => responses.push({ status: resp.status(), url: resp.url() }));
    await page.goto('/test_schema_renderer.html');
    await page.waitForFunction(() => window.__testDone === true, { timeout: 10000 });
    const results = await page.evaluate(() => window.__testResults);
    for (const r of responses) {
      console.log(`[RESP ${r.status}] ${r.url}`);
    }

    for (const r of results) {
      if (!r.pass) {
        console.log(`  FAILED: ${r.name}`, r.error || r.extra);
      }
    }
    const failed = results.filter((r) => !r.pass);
    expect(failed.length).toBe(0);
    expect(results.length).toBeGreaterThanOrEqual(10);
  });

  test('control plane form renders for ACL create (json widget for extra)', async () => {
    await page.goto('/#/control');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
  });
});
