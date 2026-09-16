import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// The Playwright project lives in frontend/, but the specs are colocated with
// the feature they cover (src/features/<feature>/e2e) and the shared fixtures
// (config.test.json, bootstrap/, uploads/) live under the repository-level tests/.
const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.join(HERE, '..');
process.env.REPO_ROOT = REPO_ROOT;

export default defineConfig({
  testDir: 'src',
  testMatch: '**/*.spec.js',
  timeout: 30000,
  expect: {
    timeout: 5000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  outputDir: path.join(REPO_ROOT, 'tests', 'test-results'),
  use: {
    baseURL: 'http://localhost:8000',
    trace: 'off-first-retry',
    screenshot: 'only-on-failure',
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || '/nix/store/9fjg59mab9j8c5r61dx2k5gcbd2f5mpm-chromium-148.0.7778.96/bin/chromium',
  },
  webServer: {
    command: 'python3 backend/manage.py --config tests/config.test.json restore --in tests/bootstrap/seed_backup.tar.gz && python3 backend/app.py --config tests/config.test.json',
    cwd: REPO_ROOT,
    url: 'http://localhost:8000',
    reuseExistingServer: false,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
