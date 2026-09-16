# Repository layout (post feature-first refactor)

The repo IS the portal. Top-level:
- `backend/` — FastAPI app. `backend/core/` (config, database, server_base, extension registry/loader, backup, auth), `backend/extensions/base.py` (BaseExtension), `backend/utils/`, and feature packages `backend/{obtainium,control_plane,app_portal,storage}/`.
- `device_agent/` — `agent.py` + `builtin_ops.py` (was `agents/`).
- `frontend/` — Svelte 5 + Vite SPA; E2E specs colocated at `frontend/src/features/<feature>/e2e/*.spec.js` and `frontend/src/shared/e2e/`.
- `tests/` — shared fixtures only (`config.test.json`, `bootstrap/seed_backup.tar.gz`, `uploads/`, `test-results/`).
- `backend/<feature>/tests/` — backend tests (core, obtainium, control_plane, app_portal); AVD harness at `backend/obtainium/tests/avd/`.
- `nixos/` — `portal-service.nix`, `portal-device-agent.nix`, `default.nix`.
- `contrib/` — non-portal assets (gamemcbe, tailscale, Android root tools) with its own `contrib/flake.nix`.

Python namespaces: `backend.*` and `device_agent.*` (repo root on sys.path). `backend/core/config.py`:
`PORTAL_DIR = ROOT_DIR =` repo root; `PUBLIC_DIR = <root>/frontend/dist`.

Entry points (pyproject): `backend.app:main` (server), `backend.manage:main`, `backend.control_plane.bridge:main`, `device_agent.agent:main`, `backend.app_portal.opencode_tool:main`.

## Extension IDs (config)
`config.EXTENSIONS` lists IDs (strings or `{id, config}`). Registry in `backend/core/extensions.py`:
`storage`, `obtainium`, `control-plane`, `app-portal`. Each extension class declares `ID`.
`{module, class}` is no longer supported. `LOADED_EXTENSIONS` is keyed by ID.
(The backup tarball still keys extension data by CLASS NAME — unchanged on-disk format.)

## Naming
`nixosModules.{portal,portal-device-agent,default}`; options `services.portal` /
`services.portal-device-agent`; units `portal`, `portal-bridge`, `portal-device-agent`;
default user/group/StateDirectory `portal`. `nixos/web-infrastructure.nix` was removed.
Flake description is portal-centric; devShell keeps `android-tools` (adb) only.

## default.nix
`src = lib.fileset.toSource { root = ./.; fileset = unions [ ./backend ./device_agent ./frontend ./pyproject.toml ./python-deps.nix ]; }`.
`propagatedBuildInputs = (import ./python-deps.nix python.pkgs) ++ [ setuptools ]` — use
`python.pkgs` (NOT a `python3Packages` arg; nixpkgs forbids `python3Packages` as a build arg).
`postInstall` copies `frontend/` into site-packages.

## Tests / commands
`make test-backend` (paths under `backend/<feature>/tests/`), `make test-e2e`
(`cd frontend && npx playwright test`; config `frontend/playwright.config.js`,
webServer cwd = repo root, fixtures in `tests/`), `make typecheck` (`cd frontend && npm run typecheck` + `mypy backend device_agent`).
Contrib: `nix develop ./contrib`, `nix build ./contrib#ksud-next`.
