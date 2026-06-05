---
name: dev-environment
description: Set up and use the development environment with nix develop and direnv
---

## What I do

Guide developers through the Nix-based development environment setup.

## Quick start

```bash
# cd to repository root (REQUIRED for nix develop)
cd /home/syoch/ghq/github.com/syoch/infrastructure

# Option 1: direnv (auto-activates on cd)
# .envrc contains "use flake" — direnv handles everything
direnv allow

# Option 2: manual nix develop
nix develop --command bash
```

## CRITICAL: pwd requirement

`nix develop` searches for `flake.nix` from the current directory.
**Always run from the repository root.** Running from a subdirectory will fail.

## Provided tools

| Category | Tools |
|----------|-------|
| Runtime | Node.js, Python 3.13 |
| Python libs | sqlalchemy, fastapi, uvicorn, python-multipart |
| Browser | Chromium (via `CHROMIUM_PATH` env var) |
| Android | aapt, android-tools (adb), dtc, usbutils |
| Network | curl, jq, nginx, certbot, openssl |
| Build | rsync, openssh, unzip, git |

## Environment variables

- `CHROMIUM_PATH` — Path to Nix-provided Chromium binary
- `DEPLOY_HOST=syoch-vpn` — Deployment target hostname
- `DEPLOY_PATH=~/infrastructure` — Deployment path on remote

## Make targets

```bash
make help              # Show all available commands
make test              # Run all tests (backend + E2E)
make test-e2e          # Playwright E2E tests only
make test-backend      # Python backend tests only
make test-obtainium    # Obtainium integration (needs BACKUP=)
make clean             # Remove test artifacts
make install-hooks     # Enable pre-commit secret scanner
```

## Notes

- Pre-commit hook scans for secrets (Tailscale auth keys, etc.)
- Test DB is SQLite at `portal/tests/portal_test.db`
- Uploads go to `portal/tests/uploads/`
- `nix develop` may take首次 ~30s to build the dev shell
