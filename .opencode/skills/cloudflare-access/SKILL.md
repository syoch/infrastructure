---
name: cloudflare-access
description: Configure Cloudflare Access path bypass for portal endpoints and troubleshoot issues
---

## What I do

Guide Cloudflare Access configuration for the portal, including path-based bypass for Obtainium compatibility.

## When to use me

Use this when:
- Obtainium shows "No suitable release found" error
- `obtainium-export.json` returns 302 instead of 200
- Downloading APKs fails through Cloudflare
- Setting up new portal endpoints behind CF Access

## Architecture

```
User/Obtainium → Cloudflare Edge → nginx (sv01) → Portal (localhost:8000)
```

- Domain: `portal.syoch.org`
- CF Access protects the entire domain
- Path bypass required for machine-to-machine endpoints

## Required path bypasses

Create Access Applications in Cloudflare Zero Trust dashboard:

| Path | Purpose |
|------|---------|
| `/scrape-index.html` | Obtainium HTML source scraping |
| `/api/apps/download/*` | APK file downloads |
| `/obtainium-export.json` | Obtainium export JSON import |

For each: Application type = Self-hosted, Policy action = Bypass.

## Download URL pattern

The download URL MUST include the filename for Obtainium's HTML source provider:

```
/api/apps/download/{apk_id}/{filename}
```

Example: `/api/apps/download/1/Arcaoid_com.Arke12917.Arcaoid_v1.0.7_arm64-v8a.apk`

Without the filename, `apkFilterRegEx` cannot match the href.

## Troubleshooting

### obtainium-export.json returns 302
- Path bypass not configured for `/obtainium-export.json`
- Check Cloudflare Zero Trust → Access → Applications

### "No suitable release found" in Obtainium
- Check scrape-index.html `<a>` tags contain filename in href
- Verify `apkFilterRegEx` matches the filename pattern
- Ensure `/api/apps/download/*` path bypass is active

### Download returns HTML instead of APK
- CF Access challenge page being returned
- Verify path bypass policy action is "Bypass" (not "Allow")

## Notes

- `cf-visitor` header detection in `utils.py` for HTTPS scheme
- `X-Forwarded-Proto` from nginx may be `http` (CF terminates TLS)
- Service Token auth is an alternative to path bypass (more secure but complex)
