---
name: portal-verify
description: Quick smoke test to verify portal server endpoints with curl
---

## What I do

Start the portal server and verify key endpoints respond correctly.
Useful for quick verification after code changes or CF Access configuration.

## When to use me

Use this for:
- Verifying CF Access path bypass is working
- Checking scrape-index.html content
- Testing download endpoint availability
- Quick smoke test without full E2E suite

## Commands

### Check endpoints (server already running)

```bash
# scrape-index.html
curl -s -o /dev/null -w "%{http_code}" "https://portal.syoch.org/scrape-index.html"

# obtainium-export.json (may return 302 if CF Access not bypassed)
curl -s -o /dev/null -w "%{http_code}" "https://portal.syoch.org/obtainium-export.json"

# APK download
curl -s -o /dev/null -w "%{http_code} %{content_type} %{size_download}" \
  "https://portal.syoch.org/api/apps/download/1/filename.apk"
```

### Start local server for testing

```bash
# pwd MUST be the repository root
nix develop --command bash -c \
  "python3 portal/manage.py --config portal/tests/config.test.json restore \
   --in portal/tests/bootstrap/seed_backup.tar.gz && \
   python3 portal/backend/main.py --config portal/tests/config.test.json"
```

## Expected results

- `scrape-index.html`: 200, `text/html`
- `obtainium-export.json`: 200 (if bypassed) or 302 (CF Access challenge)
- `/api/apps/download/{id}/{filename}`: 200, `application/vnd.android.package-archive`

## Notes

- `nix develop` requires `pwd` at repository root
- Local server runs on `http://localhost:8000`
- Check scrape-index.html `<a>` tags: href must contain filename for Obtainium matching
