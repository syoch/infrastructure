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

