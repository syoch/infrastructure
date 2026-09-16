# Repository layout (post feature-first + extension externalization)

The repo IS the portal. Top-level:
- `backend/` — core framework only: `core/` (config, database, server_base, extension registry/loader `extensions.py`, `auth.py` provider registry, backup, utils), `extensions/base.py` (BaseExtension), `app.py` (portal-server), `manage.py`.
- `extensions/` — first-party extensions, each a top-level package OUTSIDE backend, registered via entry points:
  - `extensions/obtainium/portal_obtainium/` (+ `tests/`, `tests/avd/`)
  - `extensions/control_plane/portal_control_plane/` (+ `tests/`)
  - `extensions/app_portal/portal_app_portal/` (+ `tests/`)
  - `extensions/storage/portal_storage/`
- `device_agent/` — standalone agent package (`agent.py`, `builtin_ops.py`, `protocol.py`, own pyproject/default.nix); deps websockets+jsonschema only.
- `frontend/` — Svelte 5 + Vite; E2E specs at `frontend/src/features/<feature>/e2e/`.
- `tests/` — shared fixtures only (`config.test.json`, `bootstrap/`, `uploads/`).
- `nixos/`, `contrib/`, `docs/`, `examples/`.

## Extension registration (entry points only)
`EXTENSION_REGISTRY` in `backend/core/extensions.py` is empty for first-party extensions. IDs come from
the `portal.extensions` entry-point group declared in the root `pyproject.toml`:
`storage`, `obtainium`, `control-plane`, `app-portal` → `portal_<feature>:<Class>`.
- Installed: `importlib.metadata.entry_points(group="portal.extensions")`.
- Dev/CI from source (not installed): `_repo_local_targets()` parses the root `pyproject.toml`
  `[project.entry-points."portal.extensions"]` with `tomllib` and adds each `extensions/*` dir to
  `sys.path`. No IDs are hardcoded.
- Config selects IDs: `extensions: [{"id": "...", "config": {...}}]`.

## Packaging
Single distribution `portal` (root `pyproject.toml`) with `[tool.setuptools.package-dir]` mapping
`portal_<feature>` → `extensions/<feature>/portal_<feature>`, and `[project.entry-points."portal.extensions"]`.
Entry points: `portal-server`=backend.app, `portal-manage`=backend.manage, `portal-control-bridge`=portal_control_plane.bridge,
`portal-opencode-tool`=portal_app_portal.opencode_tool. To make an extension truly third-party later, move its
pyproject/derivation out and depend on `portal` for `BaseExtension`.

## Auth decoupling
`backend/core/auth.py` holds a pluggable admin-device dependency registry
(`set_admin_device_dependency`/`get_admin_device_dependency`). Core's `api_backup.require_admin_device`
resolves it at request time (503 if unset). `portal_control_plane` registers `core.require_admin` in `setup()`.
Core never imports an extension.

## Tests / commands
`make test-backend` runs `extensions/<feature>/tests/*.py` (tests add `extensions/*` to sys.path);
`make test-e2e` = `cd frontend && npx playwright test`; `make typecheck` = svelte-check + mypy
(`backend device_agent` + each `extensions/*/portal_*`). AVD harness: `extensions/obtainium/tests/avd/`.
Contrib: `nix develop ./contrib`, `nix build ./contrib#ksud-next`.
