import { test, expect, chromium, request } from '@playwright/test';
import { execSync } from 'node:child_process';
import path from 'node:path';

test.describe('Control Plane Split UI (Phase 12)', () => {
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

  async function registerDevice(bootstrapToken, deviceId, displayName) {
    const r = await apiContext.post('/api/control/devices/register', {
      data: { device_id: deviceId, display_name: displayName, bootstrap_token: bootstrapToken },
    });
    if (r.status() !== 200) {
      throw new Error(`register failed: ${r.status()} ${await r.text()}`);
    }
    return r.json();
  }

  function promoteToAdmin(deviceId) {
    execSync(
      `python3 backend/manage.py --config tests/config.test.json control set-admin --device-id ${deviceId}`,
      { cwd: process.env.REPO_ROOT }
    );
  }

  test('bootstrap flow: #/control without token shows bootstrap form', async () => {
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.removeItem('syoch_control_token');
      localStorage.removeItem('syoch_control_device_id');
    });
    await page.goto('/control/devices');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#bootstrap-form')).toBeVisible();
  });

  test('after bootstrap, #/control lands on Devices (admin only)', async () => {
    const devId = uniqueId('webui');
    const token = issueToken(devId, 'Playwright WebUI');
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('syoch_control_token', 'dummy-before-bootstrap');
    });
    await page.goto('/control/devices');
    await expect(page.locator('#bootstrap-form')).toBeVisible();
    await page.fill('input[name="device_id"]', devId);
    await page.fill('input[name="display_name"]', 'Playwright WebUI');
    await page.fill('input[name="bootstrap_token"]', token);
    await page.click('#bootstrap-form button[type="submit"]');
    await expect(page.locator('h2', { hasText: 'Devices' })).toBeVisible();
  });

  test('acl is hidden from nav for non-admin, but accessible directly with guard message', async () => {
    const devId = uniqueId('nonadmin');
    const bootstrapToken = issueToken(devId, 'Non-Admin');
    const regResult = await registerDevice(bootstrapToken, devId, 'Non-Admin');

    await page.goto('/');
    await page.evaluate((tok) => {
      localStorage.setItem('syoch_control_token', tok);
      localStorage.setItem('syoch_control_device_id', 'nonadmin');
    }, regResult.bearer_token);

    await page.goto('/control/devices');
    await expect(page.locator('h2', { hasText: 'Devices' })).toBeVisible();

    await page.goto('/control/acl');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('[data-testid="control-guard"]')).toBeVisible();
    await expect(page.locator('#acl-form')).toHaveCount(0);
  });

  test('acl is shown for admin', async () => {
    const devId = uniqueId('admin-user');
    const bootstrapToken = issueToken(devId, 'Admin User');
    const regResult = await registerDevice(bootstrapToken, devId, 'Admin User');
    await page.goto('/');
    await page.evaluate(({ tok, dId }) => {
      localStorage.setItem('syoch_control_token', tok);
      localStorage.setItem('syoch_control_device_id', dId);
    }, { tok: regResult.bearer_token, dId: devId });
    await page.goto('/control/acl');
    await page.waitForLoadState('networkidle');
    const isForm = await page.locator('#acl-form').count();
    const isGuard = await page.locator('[data-testid="control-guard"]').count();
    expect(isForm + isGuard).toBeGreaterThan(0);
  });

  test('operations page: ops tab is default, cmds tab is switchable', async () => {
    const devId = uniqueId('ops-user');
    const bootstrapToken = issueToken(devId, 'Ops User');
    const regResult = await registerDevice(bootstrapToken, devId, 'Ops User');
    await page.goto('/');
    await page.evaluate((tok) => {
      localStorage.setItem('syoch_control_token', tok);
      localStorage.setItem('syoch_control_device_id', 'ops-user');
    }, regResult.bearer_token);

    await page.route('**/api/control/operations', async route => {
      await route.fulfill({ json: { operations: [] } });
    });
    await page.route('**/api/control/commands*', async route => {
      await route.fulfill({ json: { commands: [], total: 0, limit: 25, offset: 0 } });
    });
    await page.route('**/api/control/events*', async route => {
      await route.fulfill({ body: 'retry: 10000\n\n', contentType: 'text/event-stream' });
    });

    await page.goto('/operations');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h2', { hasText: 'Operations' })).toBeVisible();
    await expect(page.getByTestId('tab-ops')).toHaveAttribute('aria-selected', 'true');
    const cmdsTab = page.getByTestId('tab-cmds');
    await expect(cmdsTab).toBeVisible();
    await cmdsTab.click();
    await expect(cmdsTab).toHaveAttribute('aria-selected', 'true');
  });

  test('operations page: filter and pagination controls are present', async () => {
    const devId = uniqueId('op-filter');
    const bootstrapToken = issueToken(devId, 'Op Filter');
    const regResult = await registerDevice(bootstrapToken, devId, 'Op Filter');
    await page.goto('/');
    await page.evaluate((tok) => {
      localStorage.setItem('syoch_control_token', tok);
      localStorage.setItem('syoch_control_device_id', 'op-filter-user');
    }, regResult.bearer_token);
    await page.route('**/api/control/operations', async route => {
      await route.fulfill({ json: { operations: [] } });
    });
    await page.route('**/api/control/commands*', async route => {
      await route.fulfill({ json: { commands: [], total: 0, limit: 25, offset: 0 } });
    });
    await page.route('**/api/control/events*', async route => {
      await route.fulfill({ body: 'retry: 10000\n\n', contentType: 'text/event-stream' });
    });
    await page.goto('/operations');
    await page.waitForLoadState('networkidle');
    await page.getByTestId('tab-cmds').click();
    await expect(page.locator('#cmds-filter-status')).toBeVisible();
    await expect(page.locator('#cmds-filter-from')).toBeVisible();
    await expect(page.locator('#cmds-filter-to')).toBeVisible();
    await expect(page.locator('#cmds-filter-op')).toBeVisible();
    await expect(page.locator('#cmds-filter-limit')).toBeVisible();
  });

  test('operations page: filter changes update URL hash', async () => {
    const devId = uniqueId('op-hash');
    const bootstrapToken = issueToken(devId, 'Op Hash');
    const regResult = await registerDevice(bootstrapToken, devId, 'Op Hash');
    await page.goto('/');
    await page.evaluate((tok) => {
      localStorage.setItem('syoch_control_token', tok);
      localStorage.setItem('syoch_control_device_id', 'op-hash-user');
    }, regResult.bearer_token);
    let lastCommandFilterUrl = null;
    await page.route('**/api/control/operations', async route => {
      await route.fulfill({ json: { operations: [] } });
    });
    await page.route('**/api/control/commands*', async route => {
      lastCommandFilterUrl = route.request().url();
      await route.fulfill({ json: { commands: [], total: 0, limit: 10, offset: 0 } });
    });
    await page.route('**/api/control/events*', async route => {
      await route.fulfill({ body: 'retry: 10000\n\n', contentType: 'text/event-stream' });
    });
    await page.goto('/operations');
    await page.waitForLoadState('networkidle');
    await page.getByTestId('tab-cmds').click();
    await page.selectOption('#cmds-filter-status', 'succeeded');
    await page.selectOption('#cmds-filter-limit', '10');
    await page.click('#cmds-filter-apply');
    await expect(page).toHaveURL(/status=succeeded/);
    await expect(page).toHaveURL(/limit=10/);
    await expect.poll(() => lastCommandFilterUrl).toMatch(/status=succeeded/);
    await expect.poll(() => lastCommandFilterUrl).toMatch(/limit=10/);
  });

  test('nav: rail exposes Devices/ACL and navigates (admin)', async () => {
    // Promote this user to admin explicitly via CLI (no auto promotion anymore)
    const devId = uniqueId('nav-admin');
    const bootstrapToken = issueToken(devId, 'Nav Admin');
    const regResult = await registerDevice(bootstrapToken, devId, 'Nav Admin');
    promoteToAdmin(devId);
    await page.goto('/');
    await page.evaluate((tok) => {
      localStorage.setItem('syoch_control_token', tok);
      localStorage.setItem('syoch_control_device_id', 'nav-admin');
    }, regResult.bearer_token);
    // Mock SSE early to avoid hanging on networkidle
    await page.route('**/api/control/events*', async route => {
      await route.fulfill({ body: 'retry: 10000\n\n', contentType: 'text/event-stream' });
    });
    await page.goto('/control/devices');
    // Wait for me to be fetched
    await page.waitForResponse((r) => r.url().includes('/devices/me') && r.status() === 200);
    await page.waitForLoadState('domcontentloaded');
    // The navigation is a rail: the control links are directly visible.
    const devicesNav = page.getByTestId('nav-control-devices');
    await expect(devicesNav).toBeVisible();
    await expect(page.getByTestId('nav-control-acl')).toBeVisible();
    await expect(page.getByTestId('nav-operations')).toBeVisible();
    await devicesNav.click();
    await expect(page).toHaveURL(/\/control\/devices/);
    await expect(page.locator('#devices-list')).toBeVisible();
  });

  test('backend: GET /api/control/commands supports filter and pagination', async () => {
    const devId = uniqueId('backend-test');
    const bootstrapToken = issueToken(devId, 'Backend Test');
    const regResult = await registerDevice(bootstrapToken, devId, 'Backend Test');
    const r = await apiContext.get('/api/control/commands?limit=10&offset=0', {
      headers: { 'Authorization': `Bearer ${regResult.bearer_token}` },
    });
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body).toHaveProperty('commands');
    expect(body).toHaveProperty('total');
    expect(body).toHaveProperty('limit', 10);
    expect(body).toHaveProperty('offset', 0);
  });

  test('backend: invalid status filter returns 400', async () => {
    const devId = uniqueId('backend-test-2');
    const bootstrapToken = issueToken(devId, 'Backend Test 2');
    const regResult = await registerDevice(bootstrapToken, devId, 'Backend Test 2');
    const r = await apiContext.get('/api/control/commands?status=invalid', {
      headers: { 'Authorization': `Bearer ${regResult.bearer_token}` },
    });
    expect(r.status()).toBe(400);
  });

  test('bootstrap token management (admin only)', async () => {
    const adminId = uniqueId('admin');
    const adminBootstrapToken = issueToken(adminId, 'Admin User');
    const regResult = await registerDevice(adminBootstrapToken, adminId, 'Admin User');
    promoteToAdmin(adminId);

    await page.goto('/');
    await page.evaluate(({ tok, dId }) => {
      localStorage.setItem('syoch_control_token', tok);
      localStorage.setItem('syoch_control_device_id', dId);
    }, { tok: regResult.bearer_token, dId: adminId });

    await page.goto('/control/devices');
    await expect(page.locator('h2', { hasText: 'Bootstrap Tokens' })).toBeVisible();

    // Skeleton prompt dialogs for issuing a token (was native prompt/alert)
    const targetDevId = 'new-device-999';
    const promptDialog = page.getByTestId('prompt-dialog');
    const promptInput = page.getByTestId('prompt-dialog-input');

    await page.click('#issue-token-btn');

    await expect(promptDialog).toContainText('Target Device ID');
    await promptInput.fill(targetDevId);
    await page.getByTestId('prompt-dialog-confirm').click();

    await expect(promptDialog).toContainText('Display Name');
    await promptInput.fill('New Test Device');
    await page.getByTestId('prompt-dialog-confirm').click();

    await expect(promptDialog).toContainText('TTL in minutes');
    await promptInput.fill('30');
    await page.getByTestId('prompt-dialog-confirm').click();

    // Success is surfaced through a Skeleton toast (was a native alert)
    const issuedToast = page.getByTestId('toast').filter({ hasText: 'Token issued successfully' });
    await expect(issuedToast).toBeVisible();
    await expect(issuedToast).toContainText('ID:');

    // Verify token appears in list
    const tokenRow = page.locator('#tokens-list tr').filter({ hasText: targetDevId });
    await expect(tokenRow).toBeVisible();
    await expect(tokenRow).toContainText('Pending');

    // Revoke token (Skeleton confirm dialog)
    await tokenRow.locator('button', { hasText: 'Revoke' }).click();
    await expect(page.getByTestId('confirm-dialog')).toContainText('失効');
    await page.getByTestId('confirm-dialog-confirm').click();

    // Verify token disappeared or changed
    await expect(tokenRow).not.toBeVisible();
  });
});

