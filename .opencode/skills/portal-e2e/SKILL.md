---
name: portal-e2e
description: Run Playwright E2E tests for the portal dashboard and public UI
---

## What I do

Run the full Playwright E2E test suite for the portal web application.
Covers dashboard CRUD, category management, APK upload, import, and portal public UI.

## When to use me

Use this after modifying any of:
- `portal/public/js/dashboard.js`
- `portal/public/js/portal.js`
- `portal/public/js/ui.js`
- `portal/public/js/api.js`
- `portal/public/index.html`
- `portal/public/style.css`

## Command

```bash
# pwd MUST be the repository root (/home/syoch/ghq/github.com/syoch/infrastructure)
nix develop --command bash -c "cd portal/tests && npx playwright test --reporter=list"
```

Or via Make:

```bash
make test-e2e
```

## Prerequisites

- `nix develop` requires `pwd` at repository root (flake.nix lookup)
- No manual server startup needed (Playwright `webServer` config auto-starts)
- Uses Nix-provided Chromium (set via `CHROMIUM_PATH`)

## Timeout

~2 minutes for 18 tests (12 dashboard + 6 portal)

## Test structure

- `portal/tests/dashboard.spec.js` — Dashboard UI tests (12 tests)
- `portal/tests/portal.spec.js` — Public portal UI tests (6 tests)
- `portal/tests/playwright.config.js` — Config (baseURL: `http://localhost:8000`)

## Notes

- Each test creates and cleans up its own data
- Delete operations require `page.once('dialog', ...)` for confirm handling
- APK upload tests use mock binaries with `PK\x03\x04` magic bytes
- Hash-based routing: `#/dashboard`, `#/edit?type=app&id=...`
