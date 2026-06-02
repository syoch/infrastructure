#!/usr/bin/env bash
# verify.sh - check import/download/install results on the device
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Make the device's Obtainium database world-readable to adb shell run-as output
verify_db_setup() {
    # Try to enable root if the emulator allows it
    adb root >/dev/null 2>&1 || true
    sleep 1
}

# Check that an app with the given id exists in Obtainium's DB.
# Echoes "1" if found, "0" otherwise.
verify_db_has_app() {
    local app_id="$1"
    local db_path="/data/data/${OI_OBTAINIUM_PKG}/databases/Obtainium.db"
    local result
    result=$(adb shell "run-as ${OI_OBTAINIUM_PKG} sqlite3 $db_path 'SELECT COUNT(*) FROM App WHERE id = \"$app_id\"' 2>/dev/null" 2>/dev/null | tr -d '\r\n ')
    if [[ -z "$result" ]]; then
        # Fallback: try with su (rooted emulator)
        result=$(adb shell "su 0 sqlite3 $db_path 'SELECT COUNT(*) FROM App WHERE id = \"$app_id\"' 2>/dev/null" 2>/dev/null | tr -d '\r\n ')
    fi
    [[ "$result" == "1" ]] && { echo "1"; return 0; }
    echo "0"
}

# Check if the package is installed on the device
verify_package_installed() {
    local app_id="$1"
    adb shell pm list packages "$app_id" | grep -q "^package:${app_id}$"
}

# Find downloaded APK on the device; echoes the path or empty.
verify_find_apk() {
    local app_id="$1"
    local path
    path=$(adb shell "run-as ${OI_OBTAINIUM_PKG} sh -c 'find . -name \"*.apk\" 2>/dev/null'" 2>/dev/null \
        | tr -d '\r' | grep -i "$app_id" | head -1)
    echo "$path"
}

# Get the current "latest version" of an app from Obtainium's DB
verify_db_latest_version() {
    local app_id="$1"
    local db_path="/data/data/${OI_OBTAINIUM_PKG}/databases/Obtainium.db"
    adb shell "run-as ${OI_OBTAINIUM_PKG} sqlite3 $db_path 'SELECT latestVersion FROM App WHERE id = \"$app_id\"' 2>/dev/null" 2>/dev/null \
        | tr -d '\r\n'
}
