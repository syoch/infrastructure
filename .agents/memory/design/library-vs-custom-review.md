# Library-vs-custom review (2026-09)

Audited frontend / backend / test-infra for hand-rolled code that a library normally provides.
Verdict: little genuine reinvention; most custom code is justified by domain specifics
(self-hosted, nix offline packaging, bespoke WS claim/ACL/DB protocol, opaque tokens,
runtime-provided JSON Schemas). Prefer internal dedup over new deps.

## Worth adding (library)
- Frontend: `ajv` (runtime) — client currently does ZERO schema validation (only the device
  agent validates via Python `jsonschema`). Add validation before `issueCommand`
  (`Operations.svelte` + `src/lib/schema.svelte.ts`). Effort S; requires package.json dep +
  npmDepsHash update.
- Frontend: `openapi-typescript` (dev-only) — kill ~620 LOC of hand-written types + 3 duplicated
  fetch helpers (`js/api.ts`, `js/control_api.ts`, `js/app_portal_api.ts`). Payoff limited because
  NO endpoint uses `response_model=` (responses stay untyped) — do that first. Commit openapi.json
  for hermetic buildNpmPackage.
- Backend tests: `pytest` + `pytest-asyncio` + `httpx` — all in the PINNED nixpkgs (25.05);
  removes ~450-550 LOC of duplicated server-launch/port/readiness/HTTPError harness across
  test_control_plane*.py, test_app_portal*.py, test_device_agent.py. Keep real-uvicorn subprocess
  for WS fidelity (do not swap to TestClient).
- Backend: `alembic` — genuine gap: only `Base.metadata.create_all` exists, no migrations.
  Effort M-L, medium-high risk (deploy ordering vs live SQLite/Postgres; backup/restore is the
  current safety net). Only if schema keeps evolving.

## Do WITHOUT new deps (higher value)
- Dedup WS reconnect/backoff + `_http_register` between `control_plane/bridge.py` and
  `agents/device_agent.py` (near-identical).
- Dedup tiny helpers: `_slugify` (app_portal api/main_cli), `_strip_type_prefix`
  (control_plane core/manager_cli), `_parse_dt` (main.py ×2), bearer-token generator
  (manager_cli/models), APK filename (`obtainium_repo/compiler.py` vs `api.py`, comment says
  "must mirror").
- `secrets.compare_digest` for token compare in `control_plane/ws.py` (currently `!=`).
- Android test harness: 4 copies of `Automator` (fast_runner/individual_download/ui_runner/
  fast_import) + ~800 LOC dead code (fast_import.py, ui_runner.py, ui.sh dead funcs incl.
  bulk_download_all). Consolidate; delete.
- Playwright: 10× `page.waitForTimeout` + `networkidle` violate the repo no-sleep rule → use
  `expect`/`expect.poll`/`waitForResponse`.
- Nix: python dep list duplicated ~5× (pyproject, default.nix, flake.nix ×3) — centralize.

## Do NOT add
python-socketio, pluggy/stevedore, pydantic-settings/dynaconf, sse-starlette,
beautifulsoup4/lxml/selectolax (backend has NO HTML parsing; obtainium compiler only EMITS
regex strings), requests/httpx (backend — 3 tiny urllib calls), tenacity, typer/click,
fastapi-pagination, uiautomator2/adbutils/Appium (not in pinned nixpkgs; device-side agent APK;
host/docker AVD → net risk increase). Also: TanStack Query/Table (heavier than the hand-rolled
polling/pagination), foreign JSON-Schema form renderers (no mature Svelte one; schema is
runtime-provided and non-OpenAPI).

## Real bugs surfaced by the audit
- `servers/obtainium_repo/compiler.py`: "latest" APK chosen by `sorted(app.apks, key=lambda x: x.id)[-1]`
  (autoincrement row id, not semantic version) → wrong latestVersion if uploaded out of order.
- `servers/app_portal/api.py`: blocking `time.sleep(0.2)` loop (up to ~8s) inside a SYNC FastAPI
  route — violates the no-sleep rule.
- `control_plane/ws.py`: non-constant-time token comparison.
