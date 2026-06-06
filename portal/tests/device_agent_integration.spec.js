const { test, expect, chromium } = require('@playwright/test');
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

test.describe('Device Agent Integration', () => {
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

  test('full flow: issue tokens, register agent, execute command via webui', async () => {
    // 1. Issue bootstrap token for WebUI
    const webuiOut = execSync('python3 manage.py --config tests/config.test.json control issue-bootstrap-token --device-id webui --display-name "Playwright WebUI"', {
      cwd: '..'
    }).toString();
    const webuiToken = webuiOut.match(/Bootstrap token: ([\w-]+)/)[1];

    // 2. Issue bootstrap token for Agent
    const agentOut = execSync('python3 manage.py --config tests/config.test.json control issue-bootstrap-token --device-id test-agent --display-name "Test Agent"', {
      cwd: '..'
    }).toString();
    const agentToken = agentOut.match(/Bootstrap token: ([\w-]+)/)[1];

    // 3. Create Agent config
    const agentConfigPath = path.join(tempDir, 'config.json');
    const config = {
      device_id: "test-agent",
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

    // 4. Start Agent
    agentProcess = spawn('python3', ['-m', 'agents.device_agent', '--config', agentConfigPath], {
      cwd: '..',
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
    await page.fill('input[name="device_id"]', 'webui');
    await page.fill('input[name="display_name"]', 'Playwright WebUI');
    await page.fill('input[name="bootstrap_token"]', webuiToken);
    await page.click('#bootstrap-form button[type="submit"]');

    // Wait for the control dashboard to fully load (Devices tab)
    await expect(page.locator('h2', { hasText: 'Devices' })).toBeVisible();

    // 6. Verify Devices
    // WebUI should be there
    await expect(page.locator('#devices-list')).toContainText('webui');
    // test-agent should be there and online
    await expect(page.locator('#devices-list')).toContainText('test-agent');
    
    // We should see "online" for test-agent
    const testAgentRow = page.locator('#devices-list tbody tr').filter({ hasText: 'test-agent' });
    await expect(testAgentRow).toContainText('online');

    // 7. Create ACL to allow webui to command test-agent
    await page.fill('#acl-form input[name="source_device"]', 'device:webui');
    await page.fill('#acl-form input[name="target_device"]', 'device:test-agent');
    await page.fill('#acl-form input[name="operation"]', '.*');
    await page.click('#acl-form button[type="submit"]');

    // Verify ACL is added
    await expect(page.locator('#acl-tbody')).toContainText('device:webui');

    // 8. Execute Command
    const opBtn = page.locator('#ops-list button', { hasText: 'Echo Test Button' });
    await expect(opBtn).toBeVisible();
    await expect(opBtn).toBeEnabled();

    // Click the operation button
    await opBtn.click();

    // Wait for the form modal to open
    const modal = page.locator('.modal-backdrop.active');
    await expect(modal).toBeVisible();

    // Submit form to execute the command
    await modal.locator('button[type="submit"]').click();

    // 9. Verify Command Execution
    // The command list should eventually show "succeeded" and our output
    const cmdsListFirstRow = page.locator('#cmds-list tbody tr').first();
    await expect(cmdsListFirstRow).toBeVisible();
    
    // Wait until status changes to 'succeeded'
    await expect(cmdsListFirstRow.locator('td:nth-child(5)')).toHaveText('succeeded', { timeout: 10000 });
    
    // Verify result contains our echo output
    await expect(cmdsListFirstRow.locator('td:nth-child(8)')).toContainText('hello from agent integration test');
  });
});
