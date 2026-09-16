---
name: portal-e2e
description: Run Playwright E2E tests for the portal dashboard and public UI
---

## What I do

Run the full Playwright E2E test suite for the portal web application.
Covers dashboard CRUD, category management, APK upload, import, and portal public UI.

## When to use me

Use this after modifying any of:
- `frontend/src/features/obtainium/**` (dashboard, public portal, app/category modals)
- `frontend/src/shared/**` (schema renderer/form/editor)
- `frontend/src/app/**` (shell, router, toast)
- `frontend/js/api.ts`, `frontend/js/ui.ts`

## Command

```bash
# pwd MUST be the repository root (/home/syoch/ghq/github.com/syoch/infrastructure)
nix develop --command bash -c "cd frontend && npx playwright test --reporter=list"
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

~2 minutes for the full suite (dashboard, portal, control plane, app portal, schema renderer)

## Test structure

- `frontend/src/features/obtainium/e2e/dashboard.spec.js` — Dashboard UI tests
- `frontend/src/features/obtainium/e2e/portal.spec.js` — Public portal UI tests
- `frontend/src/features/control_plane/e2e/*.spec.js` — Control plane UI / device agent
- `frontend/src/features/app_portal/e2e/app_portal.spec.js` — App Portal UI
- `frontend/src/shared/e2e/schema_renderer.spec.js` — Schema renderer
- `frontend/playwright.config.js` — Config (baseURL: `http://localhost:8000`); shared fixtures in `tests/`

## Notes

- Each test creates and cleans up its own data
- Delete operations require `page.once('dialog', ...)` for confirm handling
- APK upload tests use mock binaries with `PK\x03\x04` magic bytes
- Hash-based routing: `#/dashboard`, `#/edit?type=app&id=...`
