#!/usr/bin/env bash
# verify.sh - check import/download/install results on the device
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Obtainium stores each imported app as a JSON file at
#   /data/media/0/Android/data/<pkg>/files/app_data/<id>.json
# (NOT in Obtainium.db; the SQLite file is unused for app records.)
# We use the `id` field of each JSON file to verify imports.

# Make the device's Obtainium database world-readable to adb shell run-as output.
# Calls `adb root` to enable root shell access, then waits for the device
# to come back online. Required for reading /data/media/0/.../app_data/*.
verify_db_setup() {
    adb root >/dev/null 2>&1 || true
    # adb root restarts adbd; wait for the device to be online again
    local tries=0
    while (( tries < 10 )); do
        if adb shell id 2>/dev/null | grep -q "uid=0"; then
            return 0
        fi
        sleep 1
        tries=$((tries + 1))
    done
    log_warn "verify_db_setup: adb root did not take effect; will try anyway"

    # Grant the "Install unknown apps" permission via appops so that when the
    # test triggers an install, it isn't immediately cancelled by the system.
    # (pm grant fails for this special permission; appops is the supported
    # way for automated tests on emulators.)
    adb shell appops set "${OI_OBTAINIUM_PKG}" REQUEST_INSTALL_PACKAGES allow \
        >/dev/null 2>&1 || log_warn "could not grant REQUEST_INSTALL_PACKAGES via appops"
}

# Check that an app with the given id exists in Obtainium's app_data.
# Echoes "1" if found, "0" otherwise.
verify_db_has_app() {
    local app_id="$1"
    local app_data_dir="/storage/emulated/0/Android/data/${OI_OBTAINIUM_PKG}/files/app_data"
    # Try several paths; not all devices expose /storage/emulated/0 the same way.
    # We check for file existence by looking for the path string in `ls` output.
    local result
    result=$(adb shell "ls $app_data_dir/${app_id}.json 2>/dev/null" 2>/dev/null | tr -d '\r\n ')
    if [[ -z "$result" ]]; then
        result=$(adb shell "ls /data/media/0/Android/data/${OI_OBTAINIUM_PKG}/files/app_data/${app_id}.json 2>/dev/null" 2>/dev/null | tr -d '\r\n ')
    fi
    if [[ -z "$result" ]]; then
        # Fallback: list the directory and grep for the filename
        result=$(adb shell "ls /data/media/0/Android/data/${OI_OBTAINIUM_PKG}/files/app_data/ 2>/dev/null" 2>/dev/null | grep -c "^${app_id}\.json$" 2>/dev/null)
        if [[ "$result" =~ ^[1-9][0-9]*$ ]]; then
            echo "1"
            return 0
        fi
    fi
    if [[ -n "$result" && "$result" == *"${app_id}.json"* ]]; then
        echo "1"
        return 0
    fi
    echo "0"
}

# Check if the package is installed on the device
verify_package_installed() {
    local app_id="$1"
    adb shell pm list packages "$app_id" | grep -q "^package:${app_id}$"
}

# Find downloaded APK on the device; echoes the path or empty.
# Obtainium v1.4+ stores downloaded APKs in:
#   /data/media/0/Android/data/<pkg>/cache/<id>-<hash>.apk   (downloaded)
#   /data/media/0/Android/data/<pkg>/files/app_data/<id>/    (organized per-app)
#   and the app's private files dir as well.
verify_find_apk() {
    local app_id="$1"
    local pkg="${OI_OBTAINIUM_PKG}"
    local path
    # 1) Per-app organized directory (after import organizes the APK)
    path=$(adb shell "ls /data/media/0/Android/data/${pkg}/files/app_data/${app_id}/ 2>/dev/null" 2>/dev/null \
        | tr -d '\r' | grep '\.apk$' | head -1)
    if [[ -n "$path" ]]; then
        echo "/data/media/0/Android/data/${pkg}/files/app_data/${app_id}/${path}"
        return 0
    fi
    # 2) Cache directory (downloaded but not yet organized)
    path=$(adb shell "ls /data/media/0/Android/data/${pkg}/cache/ 2>/dev/null" 2>/dev/null \
        | tr -d '\r' | grep "^${app_id}.*\.apk$" | head -1)
    if [[ -n "$path" ]]; then
        echo "/data/media/0/Android/data/${pkg}/cache/${path}"
        return 0
    fi
    # 3) Private files dir
    path=$(adb shell "run-as ${pkg} sh -c 'ls files/app_data/${app_id}/ 2>/dev/null'" 2>/dev/null \
        | tr -d '\r' | grep '\.apk$' | head -1)
    if [[ -n "$path" ]]; then
        echo "files/app_data/${app_id}/${path}"
        return 0
    fi
    # 4) Recursive search as last resort
    path=$(adb shell "find /data/media/0/Android/data/${pkg}/ -name '*.apk' 2>/dev/null" 2>/dev/null \
        | tr -d '\r' | grep -i "$app_id" | head -1)
    echo "$path"
}

# Get the current "latest version" of an app from Obtainium's app_data JSON.
verify_db_latest_version() {
    local app_id="$1"
    local path="/data/media/0/Android/data/${OI_OBTAINIUM_PKG}/files/app_data/${app_id}.json"
    adb shell "cat $path 2>/dev/null" 2>/dev/null \
        | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('latestVersion',''))
except Exception:
    pass
"
}
