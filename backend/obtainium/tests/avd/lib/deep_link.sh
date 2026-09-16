#!/usr/bin/env bash
# deep_link.sh - build and send obtainium://app/<urlencoded_json> deep links
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Build the deep link URL from an app JSON object.
# Uses Obtainium's `obtainium://app/<data>` action: home.dart wraps the path
# in {"apps": [<data>]} and calls appsProvider.import().
# Returns the URL on stdout.
build_deep_link() {
    local app_json="$1"
    python3 -c "
import json, sys, urllib.parse
app = json.loads(sys.argv[1])
url = 'obtainium://app/' + urllib.parse.quote(json.dumps(app, ensure_ascii=False))
print(url)
" "$app_json"
}

# Send a deep link to Obtainium.
send_deep_link() {
    local url="$1"
    log_debug "Deep link: ${url:0:80}..."
    adb shell am start -a android.intent.action.VIEW -d "'$url'" "$OI_OBTAINIUM_PKG" \
        >"$OI_TMP_DIR/am_start.log" 2>&1 \
        || { cat "$OI_TMP_DIR/am_start.log" >&2; die "am start failed"; }
}

# Determine whether an app in the export is self-hosted (overrideSource == HTML)
is_self_hosted_app() {
    python3 -c "
import json, sys
app = json.loads(sys.argv[1])
override = app.get('overrideSource')
apk_urls = app.get('apkUrls')
# Portal compiler emits apkUrls as a JSON string
if isinstance(apk_urls, str):
    try:
        apk_urls = json.loads(apk_urls)
    except Exception:
        apk_urls = []
print('yes' if override == 'HTML' and apk_urls else 'no')
" "$1"
}
