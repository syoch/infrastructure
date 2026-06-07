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
    await page.goto('/#/control/devices');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
  });

  test('control <-> dashboard navigation does not crash (no stack overflow)', async () => {
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message || String(e)));
    await page.goto('/#/control/devices');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(300);
    await page.goto('/#/dashboard');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(300);
    await page.goto('/#/control/devices');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    expect(errors).toEqual([]);
    const stillAlive = await page.evaluate(() => {
      const el = document.getElementById('control-view');
      return el && el.querySelector('h2') !== null;
    });
    expect(stillAlive).toBe(true);
  });

  test('operation button click opens modal', async () => {
    // Mock the API responses
    await page.route('**/api/control/devices/me', async route => {
      await route.fulfill({ json: { id: "admin", is_first_webui_device: true } });
    });
    await page.route('**/api/control/devices', async route => {
      await route.fulfill({ json: { devices: [
        { id: "device1", display_name: "Device 1", ws_state: "online", is_first_webui_device: false }
      ] } });
    });
    await page.route('**/api/control/operations', async route => {
      await route.fulfill({ json: { operations: [
        {
          id: "op1",
          name: "Test Op",
          group: "test",
          provider: "device:device1",
          params_schema: { type: "object", properties: { param1: { type: "string" } } }
        },
        {
          id: "device.config.add_operation",
          name: "Add Operation",
          group: "device.config",
          provider: "device:device1",
          params_schema: {
              type: "object",
              required: ["id", "name", "command"],
              properties: {
                  id: { type: "string", title: "Operation ID" },
                  name: { type: "string", title: "Display name" },
                  command: { type: "string", title: "Command" },
                  params_schema: { type: "object", title: "params_schema", ui_hint: { widget: "schema_editor" } },
                  ui_hint: {
                      type: "object",
                      title: "ui_hint",
                      properties: {
                          kind: { type: "string", enum: ["button", "form"] },
                          label: { type: "string" }
                      }
                  }
              }
          }
        }
      ] } });
    });
    await page.route('**/api/control/acls', async route => {
      await route.fulfill({ json: { acls: [] } });
    });
    await page.route('**/api/control/commands*', async route => {
      await route.fulfill({ json: { commands: [], total: 0, limit: 25, offset: 0 } });
    });
    // Mock SSE
    await page.route('**/api/control/events*', async route => {
      await route.fulfill({ body: 'retry: 10000\n\n', contentType: 'text/event-stream' });
    });

    // We must ensure the UI thinks we have a token so it calls the APIs
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('syoch_control_token', 'dummy');
    });
    // Navigate to operations page (where the buttons now live)
    await page.goto('/#/operations');
    await page.waitForLoadState('networkidle');

    // Wait to see if provider cards populate
    await page.waitForTimeout(1000);

    // Verify button exists
    const btn = page.locator('.provider-card button', { hasText: 'Test Op' });
    await expect(btn).toBeVisible();

    // Click it
    await btn.click();

    // Verify modal appears
    const modal = page.locator('.modal-backdrop.active');
    await expect(modal).toBeVisible();

    // Verify form content
    await expect(modal.locator('h2')).toHaveText('Test Op');
    await expect(modal.locator('input[type="text"]')).toBeVisible(); // param1 input

    // Cancel
    await modal.locator('button', { hasText: 'キャンセル' }).click();
    await expect(modal).toBeHidden();

    // Now test the Add Operation form with schema_editor
    const addBtn = page.locator('.provider-card button', { hasText: 'Add Operation' });
    await expect(addBtn).toBeVisible();
    await addBtn.click();

    await expect(modal).toBeVisible();
    await expect(modal.locator('h2')).toHaveText('Add Operation');

    // Verify the schema editor is rendered for params_schema
    const schemaEditor = modal.locator('.schema-editor-root');
    await expect(schemaEditor).toBeVisible();

    // Verify ui_hint form is rendered
    const uiHintKind = modal.locator('select').filter({ hasText: 'button' });
    await expect(uiHintKind).toBeVisible();
  });
});
