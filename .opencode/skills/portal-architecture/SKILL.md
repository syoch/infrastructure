---
name: portal-architecture
description: Understand the portal extension system, data models, and backup/restore flow
---

## What I do

Provide context about the portal server architecture for agents modifying the codebase.

## Extension system

The portal uses a plugin architecture. Extensions are loaded dynamically from config.

```
backend/core/extension_loader.py  →  Dynamically imports extension classes
backend/extensions/base.py        →  BaseExtension (abstract base)
```

Each extension can:
- Register API routes (`get_routes()`, `get_post_routes()`)
- Register CLI commands (`register_cli_commands()`)
- Provide backup/restore hooks
- Declare storage references for orphan detection

## Extensions

### StorageManagerExtension (`servers/storage_manager/`)
- Tag: `storage-provider`
- Content-Addressable Storage: files stored as `{sha256}.apk`
- Validates: max 500 MiB, must start with `PK\x03\x04`
- GC with 1-hour grace period for unreferenced files

### ObtainiumRepoExtension (`servers/obtainium_repo/`)
- Tag: `index-compiler`
- Models: `App`, `LocalAppAPK`, `Category`, `Setting`
- Compiler: generates Obtainium-compatible JSON export
- Routes: `/obtainium-export.json`, `/scrape-index.html`, `/api/apps/download/{id}/{filename}`

## Data models (`servers/obtainium_repo/models.py`)

- `App` — id, name, url, override_source, additional_settings (JSON), categories (M2M), apks (relationship)
- `LocalAppAPK` — id, app_id FK, file_hash, version, architecture
- `Category` — name, color (ARGB integer)
- `Setting` — key, value (JSON)

## Backup/Restore (`backend/core/backup_manager.py`)

- Backup: DB serialization + physical directories → `.tar.gz` with `metadata.json` + `manifest.json`
- Restore: Extract tarball, restore directories non-destructively, restore DB
- API: `GET /api/backup`, `POST /api/restore`
- CLI: `portal-manage restore --in <tarball>`

## URL generation (`servers/obtainium_repo/compiler.py`)

Self-hosted apps:
- URL: `{base_url}/scrape-index.html` (override_source: "HTML")
- APK URL: `{base_url}/api/apps/download/{apk_id}/{filename}`
- `apkFilterRegEx` and `versionExtractionRegEx` set in additionalSettings

External apps:
- URL: original app URL
- APK URLs: `["placeholder", "placeholder"]`

## Base URL detection (`servers/obtainium_repo/utils.py`)

`get_base_url()` determines public URL from:
1. `X-Forwarded-Host` or `Host` header
2. `X-Forwarded-Proto` or `cf-visitor` header (Cloudflare)
3. Falls back to `http://{local_ip}:8000`
