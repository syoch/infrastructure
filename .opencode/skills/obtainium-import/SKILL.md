---
name: obtainium-import
description: Investigate and use Obtainium's import mechanisms, including the obtainium:// deep link, in-app file picker, and the portal → Obtainium import workflow
---

## What I do

Provide a source-code-verified reference for every way to import apps into Obtainium, with concrete guidance for the portal (https://portal.syoch.org) → Obtainium workflow.

## When to use me

Use this when:
- Investigating whether `am start` / `termux-share` / FileProvider / SEND intent can feed a JSON into Obtainium
- Choosing between `obtainium://app/...`, `obtainium://apps/...`, and the in-app file picker
- Designing an automation script that pushes portal's `/obtainium-export.json` into Obtainium
- Diagnosing why a category color or setting was dropped after an import
- Deciding between deep-link automation and the manual "Import/Export" tab

## Source-code verified facts (upstream `ImranR98/Obtainium` @ `main`)

All findings come from the `ImranR98/Obtainium` repository. The portal's export format (`portal/servers/obtainium_repo/compiler.py`) is designed to be compatible with the **same** `App.fromJson` parser that Obtainium uses internally, so the round-trip is intentional.

### 1. AndroidManifest.xml — registered intent filters

`android/app/src/main/AndroidManifest.xml`:

```xml
<activity android:name=".MainActivity" ...>
    <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LAUNCHER"/>
    </intent-filter>
    <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LEANBACK_LAUNCHER"/>
    </intent-filter>
    <intent-filter>
        <action android:name="com.android_package_installer.content.SESSION_API_PACKAGE_INSTALLED" android:exported="false"/>
    </intent-filter>
    <intent-filter>
        <action android:name="android.intent.action.VIEW"/>
        <category android:name="android.intent.category.DEFAULT"/>
        <category android:name="android.intent.category.BROWSABLE"/>
        <data android:scheme="obtainium"/>
    </intent-filter>
</activity>
```

**Only `obtainium://` (VIEW) is registered.** No `SEND` intent filter, no `application/json` MIME, no FileProvider receiver. This rules out every external file-sharing path.

### 2. MainActivity.kt — no native intent handling

`android/app/src/main/kotlin/dev/imranr/obtainium/MainActivity.kt`:

```kotlin
package dev.imranr.obtainium
import io.flutter.embedding.android.FlutterActivity
class MainActivity : FlutterActivity()
```

All intent dispatch happens in Dart via the `app_links` package.

### 3. Deep link processing — `lib/pages/home.dart:240-260`

```dart
interpretLink(Uri uri) {
  var action = uri.host;       // "add" / "app" / "apps"
  var data = uri.path.substring(1);
  if (action == 'add') { ... }                              // single app by URL
  else if (action == 'app' || action == 'apps') {
    var dataStr = Uri.decodeComponent(data);
    // 1. Show a confirmation dialog (GeneratedFormModal with "Raw JSON" expansion)
    // 2. On confirm, wrap and pass to import():
    var result = await appsProvider.import(
      action == 'app'
          ? '{ "apps": [$dataStr] }'   // single app object
          : '{ "apps": $dataStr }',    // JSON array
    );
  }
}
```

Hard-coded wrapping: only `{ "apps": ... }` — the `settings` field of the input is **dropped** before reaching `import()`.

### 4. `import()` function — `lib/providers/apps_provider.dart:2163-2205`

```dart
Future<MapEntry<List<App>, bool>> import(String appsJSON) async {
  var decodedJSON = jsonDecode(appsJSON);
  var newFormat = decodedJSON is! List;
  List<App> importedApps =
      ((newFormat ? decodedJSON['apps'] : decodedJSON) as List<dynamic>)
          .map((e) => App.fromJson(e))      // per-app categories parsed here
          .toList();
  await saveApps(importedApps, onlyIfExists: false);
  if (newFormat && decodedJSON['settings'] != null) {
    var settingsMap = decodedJSON['settings'] as Map<String, Object?>;
    settingsMap.forEach((key, value) {
      if (value is int)   { settingsProvider.prefs?.setInt(key, value); }
      else if (value is double) { ... }
      else if (value is bool)   { ... }
      else if (value is List)   { ... }
      else                      { settingsProvider.prefs?.setString(key, value as String); }
    });
  }
  ...
}
```

`value as String` for the `settings.categories` case works because the portal's compiler emits that field as a **JSON-encoded string** (`json.dumps({name: color})`), not a Map.

### 5. `App.fromJson` — `lib/providers/source_provider.dart:393-438`

```dart
categories: json['categories'] != null
    ? (json['categories'] as List<dynamic>).map((e) => e.toString()).toList()
    : json['category'] != null  // backwards compat (singular)
    ? [json['category'] as String]
    : [],
```

Per-app `categories` (List<String>) is parsed and persisted in the app's individual JSON file under `${getAppStorageDir()}/app_data/${app.id}.json`.

### 6. Category color map — `lib/providers/settings_provider.dart:264-267`

```dart
Map<String, int> get categories =>
    Map<String, int>.from(jsonDecode(prefs?.getString('categories') ?? '{}'));
```

Stored in SharedPreferences under key `'categories'` as a JSON-encoded `Map<String, int>`. Read by the same getter that powers the apps page color tags.

`setCategories()` (`settings_provider.dart:269-293`) **removes any per-app category whose name is not in the map**, so an empty/missing color map = invisible categories that get wiped on the next settings edit.

## Import paths — comparison

| Method | Bulk? | Preserves `settings` (incl. category colors) | Triggerable from shell? | Confirmation dialog? |
|--------|-------|----------------------------------------------|--------------------------|----------------------|
| **In-app file picker** (Import/Export tab → Obtainium Import) | Yes | ✅ Yes | ❌ No (file_picker plugin only) | One dialog after file pick |
| **`obtainium://apps/<urlencoded JSON array>`** deep link | Yes | ❌ **No** (settings field dropped by hard-coded wrap in `home.dart:251-253`) | ✅ Yes (`am start -a VIEW`) | ✅ Always (Raw JSON shown) |
| **`obtainium://app/<urlencoded single JSON object>`** | Single only | ❌ No | ✅ Yes | ✅ Always |
| **`obtainium://add?url=<source url>`** | Single only | n/a (only URL) | ✅ Yes | ✅ Always (Add App form) |
| **`am start -a SEND` with JSON file URI** | — | — | ❌ **Rejected** (no SEND intent filter in manifest) | — |
| **`termux-share` to share JSON** | — | — | ❌ **Rejected** (same reason) | — |
| **SXncD sync (PR #2149, merged but optional server)** | Yes | Yes | ❌ Requires separate SXncD server | n/a |

## Recommended procedure (portal → Obtainium, first-time setup)

The in-app file picker is the only path that preserves **everything** (apps + settings + category colors). Shell automation is impossible for that path, and the deep link drops the `settings` field. The honest answer is **3 manual steps**:

1. **Download** `https://portal.syoch.org/obtainium-export.json` via the device browser
   - Saves to `/sdcard/Download/obtainium-export.json`
   - Requires CF Access path bypass for `/obtainium-export.json` (see `cloudflare-access` skill)
2. **In Obtainium**: ☰ → **Import/Export** → **Obtainium Import** → pick the file
3. **Confirm** the dialog (lists app count + category count), wait for the toast
4. **Install each app** manually: tap the app → **Get Latest** / **Install**

### Why not deep link?

Even with a working `am start` from nix-on-droid / termux / adb, the deep link only handles `{ "apps": ... }`. The category **colors** (`settings.categories`) are dropped, and `setCategories()` will silently wipe any orphan category names on the next settings edit. For a 30-second manual UI step that fixes this, the deep-link automation is not worth the complexity.

### nix-on-droid / Termux — what they can still contribute

```bash
# Sanity-check the downloaded JSON before opening Obtainium
nix shell nixpkgs#jq --command jq '
  { apps: (.apps | length),
    categories: (.settings.categories // "{}" | fromjson | length),
    self_hosted: [.apps[] | select(.overrideSource == "HTML")] | length }
' ~/storage/downloads/obtainium-export.json
```

This catches:
- empty `apps` array (portal misconfiguration)
- `categories` count mismatch with app references
- presence of self-hosted apps (overrideSource == "HTML"), which need a reachable base URL after the Cloudflare Access is set up

## Deep-link script (only if you accept the settings trade-off)

For environments where shell automation matters more than category colors (e.g., testing):

```bash
#!/usr/bin/env bash
# import-from-portal.sh
set -euo pipefail

# 1. Locate the JSON
SEARCH_PATHS=(
  "/mnt/storage/emulated/0/Download/obtainium-export.json"
  "/storage/emulated/0/Download/obtainium-export.json"
  "$HOME/storage/downloads/obtainium-export.json"
)
JSON_FILE=""
for p in "${SEARCH_PATHS[@]}"; do
  [ -r "$p" ] && JSON_FILE="$p" && break
done
[ -z "$JSON_FILE" ] && { echo "ERROR: JSON not found"; exit 1; }

# 2. Extract .apps, URL-encode, build deep link
APPS_JSON=$(jq -c '.apps' "$JSON_FILE")
APP_COUNT=$(echo "$APPS_JSON" | jq 'length')
ENCODED=$(printf '%s' "$APPS_JSON" | jq -sRr @uri)
DEEP_LINK="obtainium://apps/${ENCODED}"

# 3. Chunk for Android Binder limit (~500KB URL ceiling)
CHUNK=30
echo "$APPS_JSON" | python3 -c "
import json, sys, urllib.parse, subprocess
apps = json.load(sys.stdin)
for i in range(0, len(apps), $CHUNK):
    chunk = apps[i:i+$CHUNK]
    url = 'obtainium://apps/' + urllib.parse.quote(json.dumps(chunk, separators=(',', ':')))
    print(f'chunk {i//$CHUNK+1}: {len(chunk)} apps')
    subprocess.run(['am','start','-a','android.intent.action.VIEW','-d',url,'-n','dev.imranr.obtainium/.MainActivity'])
"
echo "Confirm each dialog in Obtainium"
```

**Caveats baked into the script above:**

- User must tap **Confirm** on each dialog (one per chunk). No accessibility bypass.
- Category colors are dropped (only category names survive).
- `app_links` cold-start path: a single `am start` may not deliver the URI on a slow device; the script may need a short `sleep` if cold-start races occur (rely on `app_links.getInitialLink()` which is queried in `home.dart:266-272`).
- `categories: null` in any app would still parse (becomes `[]`) — no special handling needed.

## Portal export format reference

The portal produces an Obtainium-compatible export at `https://<host>/obtainium-export.json`. Structure (compiler output):

```json
{
  "apps": [
    {
      "id": "com.example.app",
      "url": "https://...",
      "author": "...",
      "name": "Example",
      "installedVersion": null,
      "latestVersion": "1.2.3",
      "apkUrls": "[[\"filename.apk\", \"https://...\"]]",   // JSON-encoded string
      "otherAssetUrls": "[]",
      "preferredApkIndex": null,
      "additionalSettings": "{\"apkFilterRegEx\":\"...\",...}",   // JSON-encoded string
      "lastUpdateCheck": 1717000000000000,
      "pinned": false,
      "categories": ["Productivity", "Self-hosted"],
      "releaseDate": null,
      "changeLog": null,
      "overrideSource": "GitHub" | "HTML" | null,
      "allowIdChange": false,
      "pendingRepoRenameUrl": null,
      "_version": "1.2.3",                // portal-internal extras
      "_latest_apk_id": 42,
      "_filename": "Example_1.2.3.apk"
    }
  ],
  "settings": {
    "categories": "{\"Productivity\":4280391411,\"Self-hosted\":4284857472}",
    "exportSettings": 1,
    "sortColumn": 1,
    "sortOrder": 0,
    ...
  }
}
```

`apkUrls` and `additionalSettings` are intentionally **double-encoded strings** (Obtainium's `App.fromJson` expects them as strings; portal mirrors the original Obtainium `App.toJson()` shape). `categories` is a plain `List<String>` at the app level and a `Map<String,int>` JSON-encoded string at the settings level.

## Edge cases and gotchas

| Symptom | Cause |
|---------|-------|
| Deep-link import succeeds, but category tags have no color in the apps list | Normal — `settings.categories` is dropped by the deep-link wrap. Re-add in Obtainium Settings → Categories. |
| After deep-link import, an existing app's category disappears when editing settings | `setCategories()` (settings_provider.dart:269-293) removes per-app categories not in the color map. |
| `am start -a SEND` silently does nothing | Obtainium's manifest has no SEND intent filter. Confirmed in `AndroidManifest.xml`. |
| `termux-share` opens a chooser but Obtainium is not an option | Same root cause — no SEND/VIEW on JSON/text MIME. |
| Deep-link import shows a dialog with truncated Raw JSON | `App.toJson` outputs `apkUrls` and `additionalSettings` as JSON-encoded strings, so a single app can be ~1 KB. With 100+ apps, the dialog text becomes huge. |
| `obtainium://app/<long base64>` rejected by `am` with `TransactionTooLargeException` | Android Binder cap is ~1 MB per process. The encoded URL should stay under ~500 KB. Use the chunked script above. |
| After import, app "latestVersion" is null for self-hosted apps | Self-hosted apps have `apkUrls[0].value == "<base_url>/api/apps/download/<id>/<filename>"` from compiler.py:77. If the base URL is not reachable from the device, `checkUpdate` will fail; this is expected and unrelated to import. |
| Import succeeds but apps show "Override Source: HTML" with a placeholder URL | The portal's `restore_data` (`portal/servers/obtainium_repo/main.py:136-138`) sanitizes self-hosted URLs to `/scrape-index.html` on restore. The export JSON should still contain the full base URL — if the device sees a relative path, the portal config was not providing `get_base_url()` correctly. |

## Related skills and code references

- `cloudflare-access` — CF Access path bypass for `/obtainium-export.json`
- `portal-architecture` — portal's export compiler at `portal/servers/obtainium_repo/compiler.py:25-122` and the import API at `portal/servers/obtainium_repo/main.py:598-648`
- `obtainium-integration` — E2E tests that round-trip the export via AVD (uses adb, not the same path as user-driven import)
- `portal-e2e` — Playwright test `portal/tests/dashboard.spec.js:300-363` covers the inverse flow (JSON → portal DB) but the format is the same

## Test commands

```bash
# Verify portal export round-trips through Obtainium's parser
nix shell nixpkgs#jq --command bash -c '
  curl -fsS https://portal.syoch.org/obtainium-export.json \
    | jq -e ".apps | length > 0" \
    && echo "apps present" \
    || echo "no apps"
'

# Compare against the schema Obtainium uses internally
# (informational; Obtainium source is the schema of record)
nix shell nixpkgs#jq --command bash -c '
  curl -fsS https://portal.syoch.org/obtainium-export.json \
    | jq ".apps[0] | keys" -c
'
# Expected keys (subset):
# ["_filename","_latest_apk_id","_version","additionalSettings","allowIdChange",
#  "apkUrls","author","categories","changeLog","id","installedVersion",
#  "lastUpdateCheck","latestVersion","name","otherAssetUrls",
#  "overrideSource","pendingRepoRenameUrl","pinned","preferredApkIndex",
#  "releaseDate","url"]
```
