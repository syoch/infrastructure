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

# Extract the center coordinates of a node whose text or content-desc matches
# *exactly* (case-sensitive). Exact match avoids the substring trap where
# e.g. needle="Allow" would match the title "Allow Obtainium to send you
# notifications?" instead of the "Allow" button. When multiple nodes match,
# prefer the smallest (button-sized) element, falling back to the first.
# Output format: "X Y" or empty if not found.
ui_find_node_coords() {
    local dump="$1"
    local needle="$2"
    python3 - "$dump" "$needle" <<'PY'
import sys, re, xml.etree.ElementTree as ET
dump_path, needle = sys.argv[1], sys.argv[2]
tree = ET.parse(dump_path)
matches = []
for child in tree.getroot().iter():
    text = child.get('text','') or ''
    desc = child.get('content-desc','') or ''
    if needle == text or needle == desc:
        b = child.get('bounds','')
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            area = (x2 - x1) * (y2 - y1)
            matches.append((area, (x1 + x2) // 2, (y1 + y2) // 2))
if matches:
    # Pick the smallest (most button-like) match. Ties broken by first-seen order.
    matches.sort()
    _, cx, cy = matches[0]
    print(cx, cy)
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

# Tap a node whose text or content-desc *contains* the needle (substring).
# Used for compound labels like "Apps\nTab 1 of 4" where exact match would
# miss the nav tab. Returns 0 on success, 1 on miss.
ui_tap_text_contains() {
    local needle="$1"
    local dump
    dump=$(ui_dump) || return 1
    local coords
    coords=$(python3 - "$dump" "$needle" <<'PY'
import sys, re, xml.etree.ElementTree as ET
dump_path, needle = sys.argv[1], sys.argv[2]
tree = ET.parse(dump_path)
matches = []
for child in tree.getroot().iter():
    text = child.get('text','') or ''
    desc = child.get('content-desc','') or ''
    if needle in text or needle in desc:
        b = child.get('bounds','')
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            area = (x2 - x1) * (y2 - y1)
            matches.append((area, (x1 + x2) // 2, (y1 + y2) // 2))
if matches:
    matches.sort()
    _, cx, cy = matches[0]
    print(cx, cy)
PY
)
    if [[ -z "$coords" ]]; then
        log_debug "ui_tap_text_contains: '$needle' not found in current UI"
        return 1
    fi
    log_debug "ui_tap_text_contains: '$needle' -> ($coords)"
    ui_tap $coords
    return 0
}

# Wait for a node with given text to appear; polls every 1s up to timeout.
# Uses substring match (text OR content-desc contains needle) because app
# rows often have composite labels like "MicroG RE\nBy MorpheApp".
# Echoes the coordinates of the found node (or empty on timeout).
ui_wait_for_text() {
    local needle="$1"
    local timeout="${2:-30}"
    local elapsed=0
    while (( elapsed < timeout )); do
        local dump coords
        dump=$(ui_dump) || { sleep 1; elapsed=$((elapsed+1)); continue; }
        coords=$(python3 - "$dump" "$needle" <<'PY'
import sys, re, xml.etree.ElementTree as ET
dump_path, needle = sys.argv[1], sys.argv[2]
tree = ET.parse(dump_path)
for child in tree.getroot().iter():
    text = child.get('text','') or ''
    desc = child.get('content-desc','') or ''
    if needle in text or needle in desc:
        b = child.get('bounds','')
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            print((x1 + x2) // 2, (y1 + y2) // 2)
            sys.exit(0)
PY
)
        if [[ -n "$coords" ]]; then
            echo "$coords"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

# Dismiss the Obtainium first-run welcome dialog, 2026 Google Verification
# warning (the "Note" dialog), and Android system permission dialogs
# (notifications, storage, "Install unknown apps", etc.) if present.
# Best-effort: returns 0 either way. Safe to call repeatedly.
#
# Note: many Obtainium dialogs put their labels in content-desc, not text,
# so we match against both with the same exact-match rule.
#
# Special case: the system "Install unknown apps" Settings page has a
# "Allow from this source" toggle that, when tapped, flips the switch in
# place but does NOT navigate away. After toggling, we must tap "Navigate
# up" (the back arrow at top-left) to return to the calling app. Otherwise
# the Settings page stays in the foreground and blocks the rest of the
# test.
ui_dismiss_first_run() {
    local tries=0
    while (( tries < 12 )); do
        local dump
        dump=$(ui_dump) || return 0
        # Detect a dismissable dialog: any of the known button labels or
        # prompt phrases (welcome, permission, verification warning, install
        # permission for unknown sources, error dialogs from failed source
        # resolution, etc.). "Continue" is intentionally NOT listed here
        # because Obtainium's import confirmation dialog uses that
        # button — we don't want the dismiss loop to fire on it.
        if ! grep -qE '(text|content-desc)="(OK|Ok|Okay|Allow|Allow access|Allow from this source|Got it|I understand|Acknowledged|Don.t allow|Navigate up|Back)"' "$dump" 2>/dev/null \
            && ! grep -qE '(text|content-desc)="(Welcome|welcome|Allow Obtainium|send you notifications|Google Play Protect|2026|Verification|keepandroidopen|Note|Google verification|Install unknown apps|Your phone and personal data|More vulnerable|Some errors occurred|Could not find|suitable release|errors occurred)"' "$dump" 2>/dev/null; then
            return 0
        fi
        # Special case: if we're on the system "Install unknown apps" page,
        # tap the toggle and then leave via Navigate up. This must be a
        # single coordinated action — the toggle tap doesn't dismiss the
        # page on its own.
        if grep -qE 'text="(Allow from this source|Install unknown apps|Your phone and personal data)"' "$dump" 2>/dev/null; then
            if ui_tap_text "Allow from this source" 2>/dev/null; then
                log_info "Toggled 'Allow from this source' on Install unknown apps page"
            fi
            # Always press Navigate up (back arrow) to leave the page, even
            # if the toggle was already in the desired state.
            if ui_tap_text_contains "Navigate up" 2>/dev/null; then
                log_info "Pressed back from Install unknown apps page (Navigate up)"
            else
                # Fallback: BACK key if Navigate up node isn't present.
                adb shell input keyevent KEYCODE_BACK >/dev/null 2>&1 || true
                log_info "Pressed BACK from Install unknown apps page"
            fi
            sleep 1
            tries=$((tries + 1))
            continue
        fi
        # Try common positive-action button labels in priority order.
        # NOTE: "Continue" is intentionally NOT in this list — Obtainium's
        # import confirmation dialog uses a "Continue" button that the
        # test must tap explicitly (via ui_tap_text "Continue"). Tapping
        # it here would dismiss the import confirmation prematurely.
        if ui_tap_text "Allow" 2>/dev/null; then
            log_info "Dismissed permission/notification dialog (Allow)"
        elif ui_tap_text "Okay" 2>/dev/null; then
            log_info "Dismissed first-run dialog (Okay)"
        elif ui_tap_text "OK" 2>/dev/null || ui_tap_text "Ok" 2>/dev/null; then
            log_info "Dismissed first-run dialog (OK)"
        elif ui_tap_text "Got it" 2>/dev/null; then
            log_info "Dismissed first-run dialog (Got it)"
        elif ui_tap_text "I understand" 2>/dev/null; then
            log_info "Dismissed first-run dialog (I understand)"
        elif ui_tap_text "Don't allow" 2>/dev/null; then
            log_info "Dismissed permission dialog (Don't allow)"
        elif ui_tap_text_contains "Navigate up" 2>/dev/null; then
            # We're on some other system Settings page; tap the back arrow
            # to return to the previous app.
            log_info "Pressed back from system Settings page (Navigate up)"
        else
            # No known button found but a prompt is on screen; give up after this attempt
            log_debug "ui_dismiss_first_run: prompt detected but no known button"
            return 0
        fi
        sleep 1
        tries=$((tries + 1))
    done
    log_debug "ui_dismiss_first_run: gave up after $tries attempts"
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

# Swipe from (x1,y1) to (x2,y2) over `duration_ms` milliseconds. Used for
# scrolling lists. Use a duration of at least 100ms to register as a swipe
# rather than a flick/tap.
ui_swipe() {
    local x1="$1" y1="$2" x2="$3" y2="$4" duration_ms="${5:-300}"
    adb shell input swipe "$x1" "$y1" "$x2" "$y2" "$duration_ms" >/dev/null 2>&1
}

# Scroll the apps list (the main Obtainium Apps-tab list) by `direction`
# steps in `dir` ("up" to reveal entries below; "down" to reveal entries
# above). The list viewport is roughly y=200..1700 on a 1080x1920 device.
# `steps` is the number of swipe gestures to perform.
ui_scroll_apps_list() {
    local dir="${1:-up}" steps="${2:-1}"
    local x=540
    local y_top=300
    local y_bottom=1500
    local i
    for ((i = 0; i < steps; i++)); do
        if [[ "$dir" == "up" ]]; then
            # Swipe up = move finger from bottom to top = list scrolls up
            # (i.e. newer entries at the bottom become visible).
            ui_swipe "$x" "$y_bottom" "$x" "$y_top" 300
        else
            # Swipe down = move finger from top to bottom = list scrolls
            # down (i.e. older entries at the top become visible).
            ui_swipe "$x" "$y_top" "$x" "$y_bottom" 300
        fi
        # Give the list a moment to settle before the next gesture.
        sleep 0.5
    done
}

# Wait for a node with given text to appear, scrolling the apps list down
# (swiping up) to find it if it's below the fold. Stops at `max_swipes`
# swipe gestures or `timeout` seconds total, whichever comes first. On
# success, echoes the coordinates of the found node (same as
# ui_wait_for_text).
#
# Strategy: to keep this fast on slow emulators, we do a UI dump, then
# if the text wasn't found, do 2-3 consecutive swipes, then dump again.
# Each `ui_dump` call takes ~3s on the test emulator, so dumping once per
# batch of swipes is much faster than dumping after every swipe.
ui_wait_for_text_in_list() {
    local needle="$1"
    local timeout="${2:-15}"
    local max_swipes="${3:-12}"
    local swipes_per_dump="${4:-3}"
    local elapsed=0
    local swipes=0
    local dump coords
    while (( elapsed < timeout )); do
        dump=$(ui_dump) || { sleep 1; elapsed=$((elapsed+1)); continue; }
        coords=$(python3 - "$dump" "$needle" <<'PY'
import sys, re, xml.etree.ElementTree as ET
dump_path, needle = sys.argv[1], sys.argv[2]
tree = ET.parse(dump_path)
for child in tree.getroot().iter():
    text = child.get('text','') or ''
    desc = child.get('content-desc','') or ''
    if needle in text or needle in desc:
        b = child.get('bounds','')
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            # Match the apps-list area (above the bottom nav around y=1700
            # on a 1080x1920 device).
            cy = (y1 + y2) // 2
            if cy < 1700:
                print((x1 + x2) // 2, cy)
                sys.exit(0)
PY
)
        if [[ -n "$coords" ]]; then
            echo "$coords"
            return 0
        fi
        if (( swipes < max_swipes )); then
            # Do a batch of swipes, then re-dump. Swipe up moves the list
            # in the direction of newer entries (which are at the bottom
            # of the apps list on this screen).
            local to_do=$swipes_per_dump
            if (( swipes + to_do > max_swipes )); then
                to_do=$((max_swipes - swipes))
            fi
            log_debug "ui_wait_for_text_in_list: '$needle' not in viewport, batch-swiping up ($to_do swipes, $((swipes+1))..$((swipes+to_do))/$max_swipes)"
            ui_scroll_apps_list up $to_do
            swipes=$((swipes + to_do))
            elapsed=$((elapsed + 2))
            sleep 1
        else
            sleep 1
            elapsed=$((elapsed + 1))
        fi
    done
    return 1
}

# Same as ui_wait_for_text_in_list but scrolls DOWN (swiping down) — used
# to reset the list to its top before searching, in case a previous
# iteration left it scrolled.
ui_scroll_list_to_top() {
    local max_swipes="${1:-10}"
    local i
    for ((i = 0; i < max_swipes; i++)); do
        # After each swipe-down, check if the topmost app row is the
        # earliest one. Simplest heuristic: stop when a swipe-down doesn't
        # change the visible top row. For now, do a fixed number of swipes.
        ui_scroll_apps_list down 1
    done
}

# Bulk download phase: use Obtainium's "Install/update selected apps"
# bulk-install feature. Strategy:
#   1. Make sure we're on the Apps tab.
#   2. Filter to "Non-installed apps" to limit selection to installable ones.
#   3. Long-press the first app row to enter select mode.
#   4. Tap each visible app row to select it. After each tap, the count
#      in the bottom-left increases.
#   5. Scroll down to the next batch and repeat until we see the bottom
#      of the list (i.e. all apps in the filtered list are selected).
#   6. Tap "Install/update selected apps" → "Continue" to start downloads.
#   7. Wait for all APKs to land in Obtainium's cache directory.
# This replaces the slow per-app download loop, which took 30-300s per app.
# Bulk download + wait typically finishes in 2-5 minutes for 27 apps.
bulk_download_all() {
    log_info "=== Phase 2: Bulk download ==="
    # This function expects $OI_OUTPUT_DIR/report.json to exist and
    # contains the per-app import results. After the bulk download, we
    # update the report with actual download statuses.

    # Make sure Obtainium is in foreground
    adb shell am force-stop "${OI_OBTAINIUM_PKG}" >/dev/null 2>&1 || true
    adb shell am start -n "${OI_OBTAINIUM_PKG}/dev.imranr.obtainium.MainActivity" >/dev/null 2>&1 || true
    sleep 2
    ui_dismiss_first_run

    # 1. Navigate to Apps tab
    if ! ui_tap_text_contains "Tab 1 of 4" 2>/dev/null; then
        log_warn "Could not navigate to Apps tab; skipping bulk download"
        return 1
    fi
    sleep 2

    # 2. Filter to "Non-installed apps" only
    if ui_tap_text_contains "Filter apps" 2>/dev/null; then
        sleep 1
        # The "Non-installed apps" checkbox is at approximately y=1158 on
        # a 1080x1920 device. Tap it to enable filtering, then Continue.
        adb shell input tap 192 1158 2>/dev/null
        sleep 1
        if ui_tap_text "Continue" 2>/dev/null; then
            log_info "Filtered to non-installed apps"
            sleep 2
        else
            log_warn "Could not apply filter; will use all apps"
        fi
    fi
    ui_dismiss_first_run

    # 3-5. Select all apps. There is a "Select All" button in the bottom left
    # (shows the total number of apps, e.g. "27"). Tapping it selects all
    # apps in the list and enters selection mode automatically.
    # The button is at bounds [24,1464][201,1584]. Center: x=112, y=1524.
    log_info "Tapping Select All button"
    adb shell input tap 112 1524
    sleep 2

    # Verify we are in selection mode by checking the counter
    local selected=0
    local counter
    counter=$(adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1 \
        && adb pull /sdcard/ui.xml /tmp/_oi_counter.xml >/dev/null 2>&1 \
        && python3 -c "
import xml.etree.ElementTree as ET, re
t = ET.parse('/tmp/_oi_counter.xml')
for c in t.getroot().iter():
    b = c.get('bounds','')
    m = re.match(r'\[24,1464\]\[\d+,1584\]', b)
    if m:
        d = c.get('content-desc','')
        if d.isdigit():
            print(d)
            break
" 2>/dev/null || true)
    if [[ -n "${counter:-}" ]] && [[ "${counter:-0}" =~ ^[0-9]+$ ]] && (( counter > 0 )); then
        selected=$counter
        log_info "Selected $selected apps in bulk"
    else
        log_warn "Select All may have failed (counter=$counter)"
    fi

    # 6. Tap "Install/update selected apps"
    if ! ui_tap_text_contains "Install/update selected apps" 2>/dev/null; then
        log_warn "Could not tap 'Install/update selected apps' button"
        return 1
    fi
    sleep 2
    # Confirmation dialog: "Continue" triggers the actual downloads
    if ! ui_tap_text "Continue" 2>/dev/null; then
        log_warn "Could not confirm bulk install"
        return 1
    fi
    log_info "Bulk install triggered; waiting for APKs to download..."

    # 7. Wait for downloads to complete. Poll the cache directory for
    # APK files. Downloads are parallel, so we just wait for the count
    # of APKs in the cache to stabilize.
    local elapsed=0
    local last_count=-1
    local stable_polls=0
    while (( elapsed < OI_TIMEOUT )); do
        # Check if the "Pick an APK" dialog is showing (happens for unpinned
        # apps with multiple APKs in a release). We need to handle this or
        # it will block all subsequent downloads.
        local dump_file
        dump_file=$(ui_dump) || true
        if [[ -n "$dump_file" ]] && grep -q 'content-desc="Pick an APK"' "$dump_file" 2>/dev/null; then
            local unpinned_app_name
            unpinned_app_name=$(grep -oE 'content-desc="[^"]* has more than one package:"' "$dump_file" 2>/dev/null \
                | head -1 | sed 's/content-desc="//; s/ has more than one package:"//' || true)
            if [[ -n "$unpinned_app_name" ]]; then
                log_warn "Pick an APK dialog detected for: $unpinned_app_name"
                echo "$unpinned_app_name" >> "$OI_TMP_DIR/unpinned_apps.txt"
            fi
            
            local apk_coords
            apk_coords=$(python3 - "$dump_file" <<'PY'
import sys, re, xml.etree.ElementTree as ET
try:
    t = ET.parse(sys.argv[1])
    for c in t.getroot().iter():
        d = c.get('content-desc', '')
        if d.endswith('.apk'):
            b = c.get('bounds', '')
            m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
            if m:
                x1, y1, x2, y2 = map(int, m.groups())
                print(f"{(x1+x2)//2} {(y1+y2)//2}")
                sys.exit(0)
except Exception:
    pass
PY
)
            if [[ -n "$apk_coords" ]]; then
                log_debug "Tapping arbitrary APK at $apk_coords to proceed"
                ui_tap $apk_coords
                sleep 1
                ui_tap_text "Continue" 2>/dev/null || true
                sleep 2
            else
                log_debug "Could not find an APK in the list; tapping Cancel to unblock"
                ui_tap_text "Cancel" 2>/dev/null || true
                sleep 2
            fi
        fi

        # Count APKs in Obtainium's cache and app_data dirs
        local count
        count=$(adb shell "find /data/media/0/Android/data/${OI_OBTAINIUM_PKG}/ -type f -name '*.apk' 2>/dev/null | wc -l" 2>/dev/null | tr -d '\r\n ' || true)
        count=${count:-0}
        if [[ "$count" -gt 0 ]]; then
            if [[ "$count" -eq "$last_count" ]]; then
                stable_polls=$((stable_polls + 1))
            else
                stable_polls=0
            fi
            last_count=$count
            log_debug "Bulk download: $count APKs in cache (stable_polls=$stable_polls)"
            # If count has been stable for 3 polls (30s) and >0, assume done
            if (( stable_polls >= 3 )) && (( count > 0 )); then
                log_pass "Bulk download complete: $count APKs"
                break
            fi
        fi
        sleep 10
        elapsed=$((elapsed + 10))
    done

    if [[ "$elapsed" -ge "$OI_TIMEOUT" ]]; then
        log_warn "Bulk download timed out after ${OI_TIMEOUT}s ($last_count APKs found)"
    fi

    # 8. Update the report: walk through the report.json and for each
    # app, check if its APK landed in the cache. If yes, mark it as
    # downloaded; if not, mark as failed (or skipped if it wasn't
    # supposed to download, e.g. an already-installed app).
    log_info "Updating report with bulk download results..."
    local report="$OI_OUTPUT_DIR/report.json"
    if [[ ! -f "$report" ]]; then
        log_warn "Report not found at $report; cannot update"
        return 0
    fi
    # Build a list of APKs in the cache and app_data dirs for quick lookup
    local apk_list
    apk_list=$(adb shell "find /data/media/0/Android/data/${OI_OBTAINIUM_PKG}/ -type f -name '*.apk' 2>/dev/null" 2>/dev/null \
        | tr -d '\r' || true)
    # Use python to update the report
    OI_TMP_DIR="$OI_TMP_DIR" OI_OBTAINIUM_PKG="$OI_OBTAINIUM_PKG" \
        OI_APK_LIST="$apk_list" python3 - "$report" <<'PY'
import json, os, sys
report_path = sys.argv[1]
apk_list = os.environ.get('OI_APK_LIST', '')
pkg = os.environ.get('OI_OBTAINIUM_PKG', 'dev.imranr.obtainium')
tmp_dir = os.environ.get('OI_TMP_DIR', '/tmp')

# Read unpinned apps if any
unpinned_names = set()
unpinned_file = os.path.join(tmp_dir, 'unpinned_apps.txt')
if os.path.exists(unpinned_file):
    with open(unpinned_file) as f:
        unpinned_names = {line.strip() for line in f if line.strip()}

# Parse APK list to get {app_id: apk_path}
apks = {}
for line in apk_list.splitlines():
    line = line.strip()
    if not line.endswith('.apk'):
        continue
    filename = os.path.basename(line)
    # Filename format: <id>-<hash>.apk or <id>.apk or <id>_<version>.apk
    # We try to extract app ID by splitting on '-'
    if '-' in filename:
        aid = filename.rsplit('-', 1)[0]
    else:
        aid = filename.rsplit('.', 1)[0]
    apks[aid] = line

# Load report
with open(report_path) as f:
    r = json.load(f)

# Update each app's download status
for app in r.get('apps', []):
    app_id = app.get('id', '')
    app_name = app.get('name', '')
    if not app_id:
        continue
    if app_name in unpinned_names:
        app['download_status'] = 'unpinned'
        app['error_message'] = 'Pick an APK dialog appeared (unpinned)'
        continue
    
    if app_id in apks:
        app['download_status'] = 'success'
        app['apk_path'] = apks[app_id]
        app['error_message'] = None
    elif app.get('download_status') == 'skipped':
        pass  # Leave as-is
    else:
        if app.get('import_status') == 'success':
            app['download_status'] = 'failed'
            if not app.get('error_message'):
                app['error_message'] = 'APK not found in cache after bulk download'

# Update summary
s = r.get('summary', {})
s['downloaded'] = sum(1 for a in r.get('apps', []) if a.get('download_status') == 'success')
s['failed_download'] = sum(1 for a in r.get('apps', []) if a.get('download_status') == 'failed')
s['skipped'] = sum(1 for a in r.get('apps', []) if a.get('download_status') == 'skipped')
s['unpinned'] = sum(1 for a in r.get('apps', []) if a.get('download_status') == 'unpinned')
r['summary'] = s

with open(report_path, 'w') as f:
    json.dump(r, f, indent=2)

print(f'Updated report: {s["downloaded"]}/{s["total"]} downloaded, {s.get("unpinned", 0)} unpinned')
PY
}
