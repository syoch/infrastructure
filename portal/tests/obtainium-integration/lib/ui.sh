#!/usr/bin/env bash
# ui.sh - uiautomator-based UI driving helpers
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Dump the current UI tree to a temp file
ui_dump() {
    local out="${1:-$OI_TMP_DIR/ui.xml}"
    adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
    adb pull /sdcard/ui.xml "$out" >/dev/null 2>&1
    adb shell rm /sdcard/ui.xml >/dev/null 2>&1
    if [[ ! -s "$out" ]]; then
        log_debug "UI dump empty or failed: $out"
        return 1
    fi
    echo "$out"
}

# Extract the center coordinates of a node whose text or content-desc matches.
# Output format: "X Y" or empty if not found.
ui_find_node_coords() {
    local dump="$1"
    local needle="$2"
    python3 - "$dump" "$needle" <<'PY'
import sys, re, xml.etree.ElementTree as ET
dump_path, needle = sys.argv[1], sys.argv[2]
tree = ET.parse(dump_path)
def find(node):
    for child in node.iter():
        text = child.get('text','') or ''
        desc = child.get('content-desc','') or ''
        if needle in text or needle in desc:
            b = child.get('bounds','')
            m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
            if m:
                x1, y1, x2, y2 = map(int, m.groups())
                return (x1 + x2) // 2, (y1 + y2) // 2
    return None
r = find(tree.getroot())
if r:
    print(r[0], r[1])
PY
}

# Tap at coordinates
ui_tap() {
    adb shell input tap "$1" "$2" >/dev/null 2>&1
}

# Tap a node whose text or content-desc matches; returns 0 on success, 1 on miss.
ui_tap_text() {
    local needle="$1"
    local dump
    dump=$(ui_dump) || return 1
    local coords
    coords=$(ui_find_node_coords "$dump" "$needle")
    if [[ -z "$coords" ]]; then
        log_debug "ui_tap_text: '$needle' not found in current UI"
        return 1
    fi
    log_debug "ui_tap_text: '$needle' -> ($coords)"
    ui_tap $coords
    return 0
}

# Wait for a node with given text to appear; polls every 1s up to timeout.
# Echoes the coordinates of the found node (or empty on timeout).
ui_wait_for_text() {
    local needle="$1"
    local timeout="${2:-30}"
    local elapsed=0
    while (( elapsed < timeout )); do
        local dump coords
        dump=$(ui_dump) || { sleep 1; elapsed=$((elapsed+1)); continue; }
        coords=$(ui_find_node_coords "$dump" "$needle")
        if [[ -n "$coords" ]]; then
            echo "$coords"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

# Dismiss the Obtainium first-run welcome dialog and 2026 Google Verification
# warning if present. Best-effort: returns 0 either way.
ui_dismiss_first_run() {
    local tries=0
    while (( tries < 5 )); do
        local dump
        dump=$(ui_dump) || return 0
        if grep -qE 'text="(OK|Welcome|welcome|note|Note)"' "$dump" 2>/dev/null; then
            # Try to find OK / Continue button
            if ui_tap_text "OK" 2>/dev/null || ui_tap_text "Ok" 2>/dev/null; then
                log_info "Dismissed first-run dialog"
                sleep 1
            else
                break
            fi
        else
            break
        fi
        tries=$((tries + 1))
    done
}

# Tap a button with the given label; if not found, try ENTER key as fallback.
ui_confirm_button() {
    local label="${1:-Continue}"
    if ui_tap_text "$label" 2>/dev/null; then
        return 0
    fi
    log_warn "Button '$label' not found; pressing ENTER as fallback"
    adb shell input keyevent 66 >/dev/null 2>&1
    return 0
}
