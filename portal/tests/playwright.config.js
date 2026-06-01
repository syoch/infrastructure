console.log('--- PLAYWRIGHT CONFIG LOADED ---');
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: '.',
  timeout: 30000,
  expect: {
    timeout: 5000
  },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:8000',
    trace: 'off-first-retry',
    screenshot: 'only-on-failure',
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || '/nix/store/9fjg59mab9j8c5r61dx2k5gcbd2f5mpm-chromium-148.0.7778.96/bin/chromium',
  },
  webServer: {
    command: 'python3 ../manage.py --config config.test.json restore --in bootstrap/seed_backup.tar.gz && python3 ../backend/main.py --config config.test.json',
    url: 'http://localhost:8000',
    reuseExistingServer: !process.env.CI,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
