const { test, expect, chromium } = require('@playwright/test');
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

test.describe('Device Agent Integration', () => {
  test.setTimeout(60000);
  let browser;
  let context;
  let page;
  let agentProcess;
  let tempDir;

  test.beforeAll(async () => {
    browser = await chromium.launch({
      executablePath: process.env.CHROMIUM_PATH || '/nix/store/9fjg59mab9j8c5r61dx2k5gcbd2f5mpm-chromium-148.0.7778.96/bin/chromium',
      headless: true
    });
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
    page.on('pageerror', exception => {
      console.log(`[BROWSER EXCEPTION] ${exception.stack || exception}`);
    });
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log(`[BROWSER LOG] [${msg.type()}] ${msg.text()}`);
      }
    });

    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-agent-test-'));
  });

  test.afterEach(async () => {
    if (context) await context.close();

    if (agentProcess) {
      agentProcess.kill('SIGTERM');
      agentProcess = null;
    }
    if (tempDir) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  function issueToken(deviceId, displayName) {
    const out = execSync(
      `python3 manage.py --config tests/config.test.json control issue-bootstrap-token --device-id ${deviceId} --display-name "${displayName}"`,
      { cwd: path.join(__dirname, '..') }
    ).toString();
    const m = out.match(/Bootstrap token: ([\w-]+)/);
    if (!m) throw new Error(`bootstrap token not found in: ${out}`);
    return m[1];
  }

  function promoteToAdmin(deviceId) {
    return execSync(
      `python3 manage.py --config tests/config.test.json control set-admin --device-id ${deviceId}`,
      { cwd: path.join(__dirname, '..') }
    ).toString();
  }

  test('full flow: issue tokens, register agent, execute command via webui', async () => {
    // 1. Issue bootstrap token for WebUI
    const uniq = Date.now() + '-' + Math.floor(Math.random() * 1e6);
    const webuiToken = issueToken(`webui-${uniq}`, 'Playwright WebUI');

    // 2. Issue bootstrap token for Agent
    const agentToken = issueToken(`test-agent-${uniq}`, 'Test Agent');

    // 3. Create Agent config
    const agentConfigPath = path.join(tempDir, 'config.json');
    const config = {
      device_id: `test-agent-${uniq}`,
      display_name: "Test Agent",
      server_url: "http://127.0.0.1:8000",
      bootstrap_token: agentToken,
      operations: [
        {
          id: "test.echo",
          name: "Echo Test",
          group: "test",
          description: "Integration test echo",
          command: ["sh", "-c", "echo 'hello from agent integration test'"],
          shell: false,
          timeout_seconds: 10,
          ui_hint: { kind: "button", label: "Echo Test Button" },
          params_schema: { type: "object", properties: {} }
        }
      ]
    };
    fs.writeFileSync(agentConfigPath, JSON.stringify(config));

    // 4. Start Agent (cwd = portal/ so the device_agent finds the right DB module path)
    agentProcess = spawn('python3', ['-m', 'agents.device_agent', '--config', agentConfigPath], {
      cwd: path.join(__dirname, '..'),
      stdio: 'pipe',
      env: { ...process.env, PYTHONPATH: '.' }
    });
    agentProcess.stdout.on('data', d => console.log(`[AGENT] ${d.toString().trim()}`));
    agentProcess.stderr.on('data', d => console.log(`[AGENT] ${d.toString().trim()}`));

    // Allow the agent some time to connect and register
    await page.waitForTimeout(2000);

    // 5. Navigate to WebUI and Bootstrap it
    await page.goto('/#/control');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('#bootstrap-form')).toBeVisible();
    await page.fill('input[name="device_id"]', `webui-${uniq}`);
    await page.fill('input[name="display_name"]', 'Playwright WebUI');
    await page.fill('input[name="bootstrap_token"]', webuiToken);
    await page.click('#bootstrap-form button[type="submit"]');

    // Wait for the control dashboard to fully load (Devices tab)
    await expect(page.locator('h2', { hasText: 'Devices' })).toBeVisible();

    // 6. Verify Devices
    // WebUI should be there
    await expect(page.locator('#devices-list')).toContainText(`webui-${uniq}`);
    // test-agent should be there and online
    await expect(page.locator('#devices-list')).toContainText(`test-agent-${uniq}`);

    // We should see "online" for test-agent
    const testAgentRow = page.locator('#devices-list tbody tr').filter({ hasText: `test-agent-${uniq}` });
    await expect(testAgentRow).toContainText('online');

    // 7. Promote webui to admin via CLI (does not require existing admin)
    //    This makes the test self-sufficient regardless of test ordering.
    promoteToAdmin(`webui-${uniq}`);
    // Reload to refresh the admin UI state
    await page.reload();
    await expect(page.locator('h2', { hasText: 'Devices' })).toBeVisible();

    // 8. Create ACL to allow webui to command test-agent
    await page.goto('/#/control/acl');
    await page.waitForTimeout(500);
    await expect(page.locator('h2', { hasText: 'ACL' })).toBeVisible();
    await expect(page.locator('#acl-form')).toBeVisible();
    await page.fill('#acl-form input[name="source_device"]', `device:webui-${uniq}`);
    await page.fill('#acl-form input[name="target_device"]', `device:test-agent-${uniq}`);
    await page.fill('#acl-form input[name="operation"]', '.*');
    await page.click('#acl-form button[type="submit"]');

    // Verify ACL is added
    await expect(page.locator('#acl-tbody')).toContainText(`device:webui-${uniq}`);

    // 9. Execute Command via Operations page
    await page.goto('/#/operations');
    await expect(page.locator('h2', { hasText: 'Operations' })).toBeVisible();
    const opBtn = page.locator('.provider-card button', { hasText: 'Echo Test Button' });
    await expect(opBtn).toBeVisible();
    await expect(opBtn).toBeEnabled();

    // Click the operation button
    await opBtn.click();

    // Wait for the form modal to open
    const modal = page.locator('.modal-backdrop.active');
    await expect(modal).toBeVisible();

    // Submit form to execute the command
    await modal.locator('button[type="submit"]').click();

    // 10. Verify Command Execution
    // Should auto-switch to Commands tab
    await expect(page.locator('.control-tab.active', { hasText: 'Commands' })).toBeVisible();
    const cmdsListFirstRow = page.locator('#cmds-pane tbody tr').first();
    await expect(cmdsListFirstRow).toBeVisible();

    // Wait until status changes to 'succeeded'
    await expect(cmdsListFirstRow.locator('td:nth-child(5)')).toHaveText('succeeded', { timeout: 10000 });

    // Verify result contains our echo output
    await expect(cmdsListFirstRow.locator('td:nth-child(8)')).toContainText('hello from agent integration test');
  });
});
