---
name: portal-endpoint-admin-auth-verify
description: Use when adding or verifying bearer-token admin-device authentication on portal API endpoints (e.g. /api/backup, /api/restore) or when an endpoint must be admin-only: require_admin_device FastAPI dependency, frontend getToken() dynamic import, and curl 401/403/200 status-code differential against a running test server using the CLI bootstrap-token + register + set-admin flow.
---

## When to use

When an existing (or new) portal backend endpoint needs admin-only authentication — e.g. `/api/backup`, `/api/restore` — or when verifying that `require_admin_device` correctly protects an endpoint. Triggers: "add auth to endpoint", "make endpoint admin-only", "require_admin_device", "bearer token for /api/*", "backup/restore without auth", "endpoint returns 200 unauthenticated".

## Procedure

### Backend (FastAPI dependency)
1. Add a shared `require_admin_device` dependency (control-plane auth). On the endpoint, inject it as `_admin = Depends(require_admin_device)`. **Gotcha:** do NOT annotate as `_admin: Session = Depends(...)` — the dependency returns the device, not a Session; an incorrect type annotation is misleading and a future reader may pass it to DB APIs.
2. Async endpoints using `UploadFile`/`Form` need `async def`; the `Depends(...)` position is unchanged.

### Frontend (TypeScript)
1. Reuse the token helper: dynamically `const { getToken } = await import('./control_api.js')`, read `getToken()`, and only set `Authorization: Bearer <token>` when a token exists. **Gotcha:** dynamic import avoids circular-dependency import cycles; never statically import control_api in api.ts.
2. For blob downloads (backup), `fetch` with `{ headers }`, check `res.ok`, then `res.blob()` + `URL.createObjectURL` + synthetic `<a download>` click.
3. Rebuild the frontend: `cd frontend && npm run build`.

### Runtime verification via curl (status-code differential)
1. Clean state: `pkill -9 -f "manage.py|backend.app|uvicorn|_control_plane"; sleep 1; rm -f tests/portal_test.db*`; reseed: `python3 backend/manage.py --config tests/config.test.json restore --in tests/bootstrap/seed_backup.tar.gz`.
2. Start server: `cd tests && python3 ../backend/main.py --config config.test.json > /tmp/server.log 2>&1 &`; confirm `ss -ltnp | grep :8000`.
3. Expect **401/redirect without creds**: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/backup`.
4. Issue token: `python3 manage.py --config config.test.json control issue-bootstrap-token --device-id admin-dev --display-name "Admin Dev"`. Register: `POST /api/control/devices/register` with `{device_id, display_name, bootstrap_token}`; extract `bearer_token` via `python3 -c "import sys,json; print(json.load(sys.stdin)['bearer_token'])"`. Promote: `python3 manage.py --config <cfg> control set-admin --device-id admin-dev`.
5. Admin bearer must return **200**; register a second device, leave it non-admin, and confirm **403**.

### Regression
`nix develop --command bash -c "make test-backend"`, `make test-e2e`, and `nix build .#portal --no-link` (frontend + package).

## Pitfalls
- `pkill` may not free port 8000 immediately; use `kill -9 <pid>` and re-check with `ss` before starting the server.
- Always reset the DB (`rm -f tests/portal_test.db*`) between runs to avoid stale admin/device state.
- Non-admin devices still receive a valid bearer token — 403, not 401, is the correct differential.
- Don't send an empty `Authorization` header when no token exists; header-less requests hit the 401 path.
