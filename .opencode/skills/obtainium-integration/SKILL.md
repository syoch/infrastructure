---
name: obtainium-integration
description: Run Obtainium integration tests with Android emulator for APK import and download verification
---

## What I do

Run the full Obtainium integration test suite that verifies:
- Portal export JSON compilation
- APK download endpoint functionality
- Obtainium app import via deep link
- SharedPreferences hack for background update check
- Non-UI HTTP verification of APK URLs

## When to use me

Use this after modifying:
- `portal/servers/obtainium_repo/compiler.py`
- `portal/servers/obtainium_repo/main.py`
- `portal/servers/obtainium_repo/models.py`
- `portal/servers/obtainium_repo/utils.py`

## Command

```bash
# pwd MUST be the repository root
nix develop -c ./portal/tests/obtainium-integration/obtainium-integration \
  --backup-tarball /path/to/backup.tgz
```

Or via Make:

```bash
make test-obtainium BACKUP=path/to/backup.tgz
```

For a quick smoke test (3 apps):

```bash
make test-obtainium-smoke BACKUP=path/to/backup.tgz
```

## Prerequisites

- Android emulator (AVD) running with root access
- `nix develop` requires `pwd` at repository root (flake.nix lookup)
- Backup tarball path (e.g., `~/ghq/github.com/syoch/dotfiles/portal_backup_*.tar.gz`)

## Timeout

~20 minutes for 27 apps (bulk mode)

## Test modes

- `--mode bulk` — Import and download all apps (default)
- `--mode individual` — Test individual app download with HTTP verification

## Architecture

- `obtainium-integration` — Main entry point (bash)
- `lib/fast_runner.py` — Python UI automator (bulk import + download)
- `lib/individual_download.py` — Non-UI HTTP verification
- `lib/ui.sh` — UI dump and interaction helpers
- `lib/emulator.sh` — AVD management

## Notes

- Avoid `sleep`-based waiting; use `ui_dump`, file checks, or HTTP status
- GitHub API rate limit: 60/hr unauthenticated (limits bulk downloads)
- Self-hosted apps use `http://127.0.0.1:18000` (local portal)
- Results saved to `results/` directory
