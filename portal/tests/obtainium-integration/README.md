# obtainium-integration

End-to-end integration test for the Android Device Provisioning Portal.

Verifies that a **portal backup tarball**, restored into a temporary portal
instance, can be loaded into the [Obtainium](https://github.com/ImranR98/Obtainium)
Android app and that Obtainium can **actually download the APKs**.

Not part of `make test` / CI; run on demand when:

- the export JSON schema changes
- new apps are added to the portal
- new source types (GitLab, HTML, F-Droid, etc.) need verification
- Obtainium is upgraded

## How it works

1. **Restore** the user-provided backup into an isolated SQLite database
2. **Start** a temporary portal on `127.0.0.1:18000` (separate from the
   production portal on `sv01`)
3. **Start** an Android emulator (B1: local AVD, or B2: `budtmo/docker-android`)
4. **Install** the latest Obtainium APK
5. For each app in the export:
   - Force-stop and re-launch Obtainium from the launcher (so the next
     iteration always starts on the Apps tab, never stuck on the previous
     app's detail page)
   - Build `obtainium://app/<urlencoded_json>` deep link
   - Send to device via `adb shell am start`
   - Tap "Continue" on Obtainium's import dialog
   - Verify the app row appears in Obtainium's per-app JSON file
     (at `/data/media/0/Android/data/dev.imranr.obtainium/files/app_data/`)
   - Tap "Install" / "Get" / "Update" on the app detail page
   - Wait for the APK to land in Obtainium's download dir
6. Write a per-app report (JSON + text) to the output directory
7. Tear down emulator and portal (unless `--keep-*` flags are passed)

## Prerequisites

- `adb` — `nix shell nixpkgs#android-tools` (or system package)
- `curl`, `python3` (3.12+)
- For **emulator mode `local` (B1)**:
  - `ANDROID_HOME` set, with `cmdline-tools`, `platform-tools`, `emulator`,
    and a `system-images;android-34;google_apis;x86_64` (or `arm64-v8a`) image
  - KVM access (`/dev/kvm` readable)
- For **emulator mode `docker` (B2)**:
  - Docker
  - KVM access
- For self-hosted apps in the export: nothing extra (the test portal is
  exposed to the device via `adb reverse`)

## Quick start

```bash
# From the infrastructure repo root
make test-obtainium BACKUP=~/backups/portal-backup-20260601.tgz

# Smoke test (3 apps only)
make test-obtainium-smoke BACKUP=~/backups/portal-backup-20260601.tgz

# Or invoke the script directly. Wrap in `nix develop -c` to get the
# matching Python/tarfile/argparse environment.
nix develop -c ./portal/tests/obtainium-integration/obtainium-integration \
  --backup-tarball ~/backups/portal-backup-20260601.tgz

# With explicit options
nix develop -c ./portal/tests/obtainium-integration/obtainium-integration \
  --backup-tarball ~/backups/portal-backup-20260601.tgz \
  --emulator-mode docker \
  --apps 5 \
  --filter 'github.com' \
  --output-dir ./results
```

## Options

```
--backup-tarball PATH        Portal backup tarball (required)
--emulator-mode MODE         auto|local|docker (default: auto)
--output-dir DIR             Where to write report (default: ./results/.../<ts>)
--apps N                     Only test the first N apps
--filter REGEX               Only test apps whose id/name matches REGEX
--skip-source-html           Skip self-hosted apps (overrideSource=HTML)
--skip-download              Skip APK download trigger/verification
--timeout SECONDS            Per-app timeout (default: 300)
--obtainium-version VER      Obtainium release tag (default: latest)
--keep-portal                Don't stop the test portal on exit
--keep-emulator              Don't stop the emulator on exit
--keep-tmp                   Don't delete the per-run tmp dir on exit
--no-color                   Disable colored output
--debug                      Verbose debug logging
-h, --help                   Show this help
```

## Reports

Both written to `--output-dir`:

- `report.json` — machine-readable, structured per-app + summary
- `report.txt` — human-readable, sorted by app

Per-app fields:

| Field | Meaning |
|---|---|
| `import_status` | `success` / `failed` / `skipped` |
| `download_status` | `success` / `failed` / `skipped` |
| `duration_seconds` | wall time per app |
| `apk_path` | where the downloaded APK landed on the device (if found) |
| `error_message` | non-null on failure |

Exit code: `0` if all imports and downloads succeeded, `1` otherwise.

## Known limitations

- **Confirmation dialog UI driving**: the script uses `uiautomator dump` +
  `input tap` to click "Continue". If Obtainium's UI changes (new button
  text, different layout), the matcher in `lib/ui.sh:ui_confirm_button` may
  need updating.
- **First-run dialogs**: the welcome dialog, 2026 Google Verification
  warning, and the Android "Install unknown apps" permission dialog are
  dismissed best-effort. If the device has a clean slate, the script taps
  "OK" / "Allow from this source" / etc. up to 12 times.
- **Apps list visibility**: the test only sees apps that are visible in
  the Apps tab viewport. If the apps list is long, newly-imported apps
  may be below the fold and the test reports `App entry not visible on
  apps list after 15s`. This currently affects some apps in the
  27-app backup but not the 3-app smoke test.
- **Download step depends on UI**: not all apps expose an "Install" / "Get"
  / "Update" button. If none is found, `download_status="skipped"` with a
  descriptive error.
- **Self-hosted apps**: rely on `adb reverse tcp:18000 tcp:18000` so the
  device can reach the test portal. If a self-hosted app's source URL is
  rewritten incorrectly, it will fail.
- **Network flakiness**: A3 hits GitHub / GitLab / etc. for real. A single
  app timing out does not abort the suite (per-app `failed` status), but
  total runtime can be long (about 40s per app on a warm emulator, plus
  ~30-90s of first-run/dialog handling on the first iteration).
- **No CI integration**: by design. KVM + emulator boot is too slow for
  every-PR testing.

## File layout

```
obtainium-integration/
├── obtainium-integration     main script (CLI + flow control)
├── Makefile                  `make run` / `make smoke` / `make clean`
├── README.md                 this file
├── lib/
│   ├── common.sh             logging, color, cleanup hooks
│   ├── emulator.sh           B1 (AVD) / B2 (docker) launch
│   ├── obtainium.sh          APK fetch + install
│   ├── portal.sh             restore tarball + start test portal + adb reverse
│   ├── deep_link.sh          build `obtainium://app/<urlencoded>` URL
│   ├── ui.sh                 uiautomator dump + tap helpers
│   ├── verify.sh             DB / package / APK presence checks
│   ├── report.sh             JSON + text report generation
│   └── filter_apps.py        app filter helper (--apps, --filter, --skip-source-html)
├── fixtures/                 reserved for sample data
└── results/                  output directory (gitignored)
```

## Troubleshooting

- **Boot timeout** — emulator did not finish booting. Check
  `$TMPDIR/obtainium-integration-*/emulator.log` for details.
- **adb install fails** — usually Obtainium APK download incomplete. Check
  `~/.cache/obtainium-integration/`. Delete and re-run.
- **Confirmation dialog not detected** — Obtainium's UI may have changed.
  Manually inspect: `adb shell uiautomator dump /sdcard/ui.xml && adb pull
  /sdcard/ui.xml`. Update `lib/ui.sh:ui_confirm_button` to match the actual
  button text.
- **DB query returns empty** — the script falls back from `run-as` to `su 0`
  for rooted emulators. If neither works, check
  `adb shell getprop ro.build.type` (should be `userdebug` for rooted).
- **All apps skipped** — check the export file:
  `python3 -c "import json; print(len(json.load(open('export.json'))['apps']))"`
  Also verify the filter regex doesn't exclude everything.
- **Run with `--debug --keep-tmp`** to keep UI dumps (`diag_*.xml` and
  `ui.xml`) and verbose logs in the per-run tmp dir. The diagnostic
  output includes a short screen summary like
  `screen[pre_<appid>]: D=Apps | MicroG RE | 1 | ...` so you can see
  what's on screen at each iteration.
