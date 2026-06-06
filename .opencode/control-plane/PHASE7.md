# Phase 7 — Portal Device Agent

**Status**: DONE

## Goal
Provide a generic, JSON-config-driven device agent that connects to the control
plane over WebSocket, advertises a set of operations, and executes incoming
commands as local shell commands. Configurable from the portal WebUI itself
(via built-in operations), reloadable via SIGHUP.

## Files added
- `portal/agents/__init__.py` — empty
- `portal/agents/device_agent.py` — main agent daemon (entry point: `portal-device-agent`)
- `portal/agents/builtin_ops.py` — 7 built-in operations
- `nixos/portal-device-agent.nix` — NixOS service module
- `portal/tests/backend/test_device_agent.py` — 36 tests (35 unit + 1 integration)
- `docs/portal-device-agent-termux.md` — Termux:Boot setup

## Files changed
- `pyproject.toml`: added `portal-device-agent` entry point, `jsonschema` + `websockets` deps
- `portal/default.nix`: added `jsonschema` to propagatedBuildInputs
- `flake.nix`: added `jsonschema` to devShell / test-backend / test-e2e; added NixOS module export
- `Makefile`: added `test_device_agent.py` to test-backend
- `portal/public/js/control_op_renderer.js`: added `widget: "json"` / `widget: "textarea"` support

## Built-in operations
1. `device.config.list_operations` (button) — returns current user operations
2. `device.config.add_operation` (form) — fields: id, name, group, description, command, shell, timeout, params_schema (json widget), ui_hint (json widget)
3. `device.config.update_operation` (form) — same fields, replaces existing
4. `device.config.delete_operation` (form) — id
5. `device.config.test_operation` (form) — id + params (json widget); runs locally
6. `device.config.get_config` (button) — returns raw config.json text
7. `device.config.reload` (button, confirm) — re-reads config.json, re-registers

## Config schema
```json
{
  "device_id": "my-server",
  "display_name": "My Server",
  "server_url": "https://portal.syoch.org",
  "bootstrap_token": "tk_xxx",
  "bootstrap_token_file": "/run/agenix/portal-device-agent-bootstrap",
  "credentials_file": "/var/lib/syoch-portal-device-agent/credentials.json",
  "operations": [
    {
      "id": "system.reboot",
      "name": "Reboot",
      "group": "system",
      "description": "Reboot this device",
      "command": ["systemctl", "reboot"],
      "shell": false,
      "timeout_seconds": 30,
      "ui_hint": {"kind": "button", "label": "Reboot", "confirm": true, "danger": true},
      "params_schema": {"type": "object", "properties": {}}
    }
  ]
}
```

## Lifecycle
1. Load `config.json` (jsonschema-validated)
2. If `credentials_file` exists with valid `bearer_token`, reuse it; otherwise
   call `POST /api/control/devices/register` with the bootstrap token and save
   the resulting `bearer_token` to `credentials_file` (chmod 0o600).
3. Open WebSocket to `/api/control/devices/{id}/ws?token={bearer}`
4. Receive `welcome` (with `pending_commands`); process each.
5. Send `operations_register` (built-in + user).
6. Main loop: receive `command` pushes; for each → `claim` → execute → `result`.
7. On `bye` or disconnect: exponential backoff reconnect (1s → 30s cap), then re-register.
8. SIGHUP: schedule reload — re-read config, send new `operations_register` on the same WS.
9. SIGTERM/SIGINT: graceful shutdown.

## Command execution
- `command` is `str` or `list[str]`.
- `{name}` placeholders are substituted with `str(params[name])`.
- If `shell: true` (or command is a `str` with shell metacharacters needed):
  - For `list`: joined with `shlex.quote` on each element, run via `sh -c`.
  - For `str`: run via `sh -c`.
- `params` are validated against `params_schema` (jsonschema Draft7).
- `subprocess.run(..., timeout=timeout_seconds, capture_output=True, text=True)`
- Result: `{stdout, stderr, exit_code, duration_ms}`. Succeeded iff exit_code == 0.

## Renderer extension (Phase 7 scope)
- `property.ui_hint.widget === "json"` → render `<textarea rows=6>`, parse on submit
- `property.ui_hint.widget === "textarea"` → render `<textarea rows=3>`
- `object` / `array` types without `widget` continue to be skipped (Phase 10)

## NixOS module
- `services.syoch-portal-device-agent.enable`
- `configFile` (path to config.json)
- `bootstrapTokenFile` (optional path to bootstrap token, used only on first run)
- `serverUrl` (default: `http://127.0.0.1:8000`)
- `user`, `group`, `stateDirectory` for isolation
- Hardened systemd sandbox (`ProtectSystem=strict`, `NoNewPrivileges`, etc.)

## Android (Termux + nix-on-droid)
- `~/.termux/boot/portal-device-agent.sh` — waits for Tailscale connectivity, then execs the agent
- Config lives at `~/.config/portal-device-agent/config.json` (or wherever the script points)
- nix-on-droid provides the `portal-device-agent` binary via `nix-on-droid -- run portal-device-agent --config <path>`

## Test summary
```
[unit: interpolate / build_command] 7 tests
[unit: validate_params] 2 tests
[unit: execute_shell] 3 tests
[unit: load/save config] 4 tests
[unit: agent built-in ops] 12 tests
[unit: built-in ops introspection] 3 tests
[integration: agent with real server] 1 test (register → WS → claim → execute → result)
Total: 32 device-agent tests
+ 24 REST + 5 WS + 3 backup tests already in the suite
```

## Known limitations
- No visual schema editor (Phase 10)
- No UI for the agent itself (config is edited via portal WebUI, using the
  built-in `device.config.add_operation` / `update_operation` / `delete_operation`
  forms with `widget: "json"` for the complex fields)
- No automatic re-register when only `ui_hint` or `params_schema` change
  (SIGHUP is required, or `device.config.reload`)
- No concurrent command execution (serial, one at a time)
