import { test, expect, chromium, request } from '@playwright/test';
import { execSync } from 'node:child_process';
import path from 'node:path';

test.describe('App Portal UI', () => {
  let browser;
  let context;
  let page;
  let apiContext;
  let counter = 0;

  test.beforeAll(async () => {
    browser = await chromium.launch({
      executablePath: process.env.CHROMIUM_PATH || '/nix/store/9fjg59mab9j8c5r61dx2k5gcbd2f5mpm-chromium-148.0.7778.96/bin/chromium',
      headless: true,
    });
    apiContext = await request.newContext({ baseURL: 'http://localhost:8000' });
  });

  test.afterAll(async () => {
    if (browser) await browser.close();
    if (apiContext) await apiContext.dispose();
  });

  test.beforeEach(async () => {
    context = await browser.newContext({ baseURL: 'http://localhost:8000' });
    page = await context.newPage();
    page.on('pageerror', (e) => console.log(`[BROWSER EXCEPTION] ${e.stack || e}`));
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log(`[BROWSER ERROR] ${msg.text()}`);
    });
  });

  test.afterEach(async () => {
    if (context) await context.close();
  });

  function uniqueId(prefix) {
    counter += 1;
    return `${prefix}-${Date.now()}-${counter}-${Math.floor(Math.random() * 1e6)}`;
  }

  function issueToken(deviceId, displayName) {
    const out = execSync(
      `python3 backend/manage.py --config tests/config.test.json control issue-bootstrap-token --device-id ${deviceId} --display-name "${displayName}"`,
      { cwd: process.env.REPO_ROOT }
    ).toString();
    const m = out.match(/Bootstrap token: ([\w-]+)/);
    if (!m) throw new Error(`bootstrap token not found in: ${out}`);
    return m[1];
  }

  function promoteToAdmin(deviceId) {
    execSync(
      `python3 backend/manage.py --config tests/config.test.json control set-admin --device-id ${deviceId}`,
      { cwd: process.env.REPO_ROOT }
    );
  }

  async function registerDevice(bootstrapToken, deviceId, displayName) {
    const r = await apiContext.post('/api/control/devices/register', {
      data: { device_id: deviceId, display_name: displayName, bootstrap_token: bootstrapToken },
    });
    if (r.status() === 409) {
      // already registered (shared server across specs) — look up the token via list
      return null;
    }
    if (r.status() !== 200) throw new Error(`register failed: ${r.status()} ${await r.text()}`);
    return r.json();
  }

  test('apps route requires a control-plane token (redirects to #/control)', async () => {
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.removeItem('syoch_control_token');
      localStorage.removeItem('syoch_control_device_id');
    });
    await page.goto('/#/apps');
    await page.waitForLoadState('domcontentloaded');
    await expect(page).toHaveURL(/#\/control/);
  });

  test('register app, open detail, submit feedback', async () => {
    const devId = uniqueId('apps-admin');
    const bootstrapToken = issueToken(devId, 'Apps Admin');
    const reg = await registerDevice(bootstrapToken, devId, 'Apps Admin');
    promoteToAdmin(devId);

    // Register the bridge device so feedback commands can be enqueued (target FK).
    await registerDevice(issueToken('opencode-bridge', 'OpenCode Bridge'), 'opencode-bridge', 'OpenCode Bridge');

    await page.goto('/');
    await page.evaluate((tok) => {
      localStorage.setItem('syoch_control_token', tok);
    }, reg.bearer_token);

    await page.goto('/#/apps');
    await expect(page.locator('#apps-view h2', { hasText: 'アプリ' })).toBeVisible();

    // Register an app through the UI form
    await page.click('#app-register-toggle');
    const appName = `E2E App ${Date.now()}`;
    await page.fill('#app-register-form input[name="name"]', appName);
    await page.fill('#app-register-form input[name="description"]', 'created by e2e');
    await page.fill('#app-register-form input[name="url"]', 'http://127.0.0.1:5173');
    await page.fill('#app-register-form input[name="project_directory"]', `/tmp/e2e-${Date.now()}`);
    await page.fill('#app-register-form input[name="opencode_session_id"]', 'ses_e2e_test');
    await page.fill('#app-register-form input[name="tags"]', 'e2e, web');
    await page.click('#app-register-form button[type="submit"]');

    const card = page.locator('#apps-list .provider-card', { hasText: appName });
    await expect(card).toBeVisible();

    // Open detail
    await card.click();
    await expect(page.locator('#feedback-form')).toBeVisible();
    await expect(page.locator('code', { hasText: 'ses_e2e_test' })).toBeVisible();

    // Submit feedback (no bridge -> stays pending)
    await page.selectOption('#feedback-form select[name="kind"]', 'bug');
    await page.fill('#feedback-form textarea[name="body"]', 'これはE2Eテストのフィードバックです');
    await page.click('#feedback-form button[type="submit"]');

    const history = page.locator('#feedback-history');
    await expect(history).toContainText('これはE2Eテストのフィードバックです');
    await expect(history).toContainText('pending');
    await expect(history).toContainText('bug');
  });

  test('edit registered app settings', async () => {
    const devId = uniqueId('apps-edit');
    const bootstrapToken = issueToken(devId, 'Apps Edit');
    const reg = await registerDevice(bootstrapToken, devId, 'Apps Edit');
    promoteToAdmin(devId);

    const auth = { Authorization: `Bearer ${reg.bearer_token}` };
    const appName = `Edit App ${Date.now()}`;
    const created = await apiContext.post('/api/app-portal/apps', {
      headers: auth,
      data: {
        name: appName,
        description: 'before',
        project_directory: `/tmp/edit-${Date.now()}`,
        opencode_session_id: 'ses_edit',
        tags: ['old'],
      },
    });
    expect(created.status()).toBe(200);
    const app = await created.json();

    try {
      await page.goto('/');
      await page.evaluate((tok) => localStorage.setItem('syoch_control_token', tok), reg.bearer_token);
      await page.goto(`/#/apps/${app.slug}`);
      await expect(page.locator('#app-edit-form')).toBeVisible();

      const newName = `${appName} (edited)`;
      await page.fill('#app-edit-form input[name="name"]', newName);
      await page.fill('#app-edit-form input[name="description"]', 'edited description');
      await page.fill('#app-edit-form input[name="tags"]', 'new, tags');
      await page.selectOption('#app-edit-form select[name="status"]', 'archived');
      await page.click('#app-edit-form button[type="submit"]');

      // Re-rendered header + form reflect the new values
      await expect(page.locator('h2', { hasText: newName })).toBeVisible();
      await expect(page.locator('#app-edit-form input[name="description"]')).toHaveValue('edited description');
      await expect(page.locator('#app-edit-form select[name="status"]')).toHaveValue('archived');

      // Persisted server-side
      const fetched = await apiContext.get(`/api/app-portal/apps/${app.slug}`, { headers: auth });
      const detail = await fetched.json();
      expect(detail.name).toBe(newName);
      expect(detail.description).toBe('edited description');
      expect(detail.status).toBe('archived');
      expect(detail.tags).toEqual(['new', 'tags']);
    } finally {
      await apiContext.delete(`/api/app-portal/apps/${app.slug}`, { headers: auth });
    }
  });
});
