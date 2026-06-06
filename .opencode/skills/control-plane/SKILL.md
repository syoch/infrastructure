---
name: control-plane
description: Use when working on the portal control plane (devices, ACLs, operations, commands, WebSocket, bridge.py) - explains the dogfooding architecture, data model, and message protocols
---

## What it is

The control plane is a portal extension that lets devices advertise operations,
receive commands, and have them dispatched via WebSocket. The WebUI (`#/control`)
acts as an admin dashboard.

## Dogfooding architecture

The server does **not** provide any operations itself. Instead, a `bridge.py`
process is a regular device that connects via WebSocket and provides
`acl.*` / `device_admin.*` operations by invoking `portal-manage control ...`
subprocesses. This keeps ACL evaluation consistent (no special-casing for
"the server itself").

## Data model (5 tables)

| Table | Purpose |
|-------|---------|
| `ctrl_devices` | Registered devices (id, display_name, bearer_token, ws_state, is_first_webui_device) |
| `ctrl_device_acls` | ACL rules: source_device / target_device / operation are all regex |
| `ctrl_bootstrap_tokens` | One-time tokens for new device registration |
| `ctrl_operation_specs` | (provider, id) composite PK; provider LIKE 'device:%' CHECK constraint |
| `ctrl_command_requests` | pending → claimed → succeeded/failed/timeout/cancelled |

## REST API (under `/api/control/`)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `POST` | `/devices/register` | bootstrap_token | Returns bearer_token |
| `GET` | `/devices/me` | any | Triggers first-webui-device auto-promote |
| `GET` | `/devices` | any | List all devices |
| `PATCH` | `/devices/{id}` | any (self) or admin | Update display_name |
| `DELETE` | `/devices/{id}` | admin | |
| `POST` | `/devices/{id}/set-admin` | admin | |
| `GET` | `/acls` | any | List ACL rules |
| `POST` | `/acls` | admin | Create rule |
| `PATCH` | `/acls/{id}` | admin | |
| `DELETE` | `/acls/{id}` | admin | |
| `GET` | `/operations` | any | Filtered: admin sees all, others see only those they can ACL-target |
| `POST` | `/commands` | any | ACL-checked; pushes via WS |
| `GET` | `/commands` | any | List (filtered: own or admin) |
| `GET` | `/commands/{id}` | source or admin | |
| `GET` | `/events` | any | SSE stream |
| `WS` | `/devices/{id}/ws?token=tk_xxx` | via query | Device protocol |

## WebSocket protocol

Client → Server:
- `hello` `{resumed_claimed_ids?: [...]}` (reconnect resume)
- `ping` `{}`
- `claim` `{command_id, claim_token}`
- `result` `{command_id, status: "succeeded"|"failed", result?, error?}`
- `operations_register` `{operations: [{id, name, group, params_schema, ui_hint, ...}]}`

Server → Client:
- `welcome` `{device_id, display_name, is_first_webui_device, pending_commands: [...]}`
- `command` `{command_id, operation, params, timeout_seconds, claim_token, source_device_id}`
- `claimed_ack` `{command_id}`
- `result_ack` `{command_id, status}`
- `operations_registered` `{count}`
- `pong` `{}`
- `bye` `{reason}`
- `error` `{message}`

## ACL evaluation

`can_issue(db, source_id, target_id, operation)` walks all ACLs and returns True if any
ACL matches via `re.search` on the **pattern part** of each `device:<regex>` field.
source/target/operation are all required to match. Default-deny.

## Sync → async push problem

`enqueue_command` is called from a FastAPI sync handler (anyio threadpool).
The WS lives on the main event loop. The dispatcher captures the main loop via
`set_main_loop` (called from `@app.on_event("startup")` in
`ControlPlaneExtension.install_event_loop_capture`), then uses
`asyncio.run_coroutine_threadsafe(...)` to schedule the push.

## Files

```
portal/servers/control_plane/
  __init__.py
  main.py        # ControlPlaneExtension (BaseExtension)
  models.py      # 5 tables
  manager_cli.py # 13 `portal-manage control ...` subcommands
  auth.py        # get_current_device (header or ?token=), get_current_device_with_promotion, require_admin
  dispatcher.py  # can_issue, resolve_provider, provider_device_id, filter_operations_for_device, enqueue_command
  api.py         # 14 REST endpoints
  ws.py          # ConnectionManager, device_ws, message handlers, notify_command
  sse.py         # EventBus + /events endpoint
  bridge.py      # Dogfood: serves acl.* and device_admin.* as a normal device
```

## Bootstrap flow for WebUI

```bash
# 1. server-side: issue bootstrap token
portal-manage control issue-bootstrap-token --device-id webui --display-name "WebUI"

# 2. open WebUI: http://localhost:8000/#/control
# 3. paste the token, save bearer_token to localStorage
# 4. first /devices/me call auto-promotes to admin (last-writer-wins)
```

## Bootstrap flow for bridge

```bash
# 1. server-side: issue bootstrap token (long-lived)
portal-manage control issue-bootstrap-token --device-id bridge --display-name "Portal Bridge"

# 2. systemd starts portal-control-bridge
portal-control-bridge \
  --server-url http://127.0.0.1:8000 \
  --bootstrap-token $(cat /run/secrets/portal-bridge-token) \
  --config /var/lib/syoch-portal/config.json
```

## Tests

- `portal/tests/backend/test_control_plane.py` (24 REST tests, no nix-only deps)
- `portal/tests/backend/test_control_plane_ws.py` (5 WS tests, requires `nix develop`)

Run all backend tests: `make test-backend`

## More

Full design docs: `.opencode/control-plane/PHASE{1..6}.md`
