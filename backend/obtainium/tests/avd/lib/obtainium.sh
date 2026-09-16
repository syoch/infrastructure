#!/usr/bin/env bash
# obtainium.sh - fetch and install the Obtainium APK
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Determine the latest release version (or use OI_OBTAINIUM_VERSION)
obtainium_latest_version() {
    curl -sf "https://api.github.com/repos/ImranR98/Obtainium/releases/latest" \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'])"
}

# Download the APK if not cached; returns the cached path
obtainium_fetch_apk() {
    local version="${1:-$(obtainium_latest_version)}"
    [[ -n "$version" ]] || die "Could not determine Obtainium version"

    local apk_name="Obtainium-${version}.apk"
    local cache_path="$OI_CACHE_DIR/$apk_name"

    if [[ -f "$cache_path" ]]; then
        log_info "Using cached APK: $cache_path"
        echo "$cache_path"
        return 0
    fi

    local url="https://github.com/ImranR98/Obtainium/releases/download/${version}/app-release.apk"
    log_info "Downloading $apk_name from $url"
    if ! curl -fL -o "$cache_path" "$url"; then
        log_warn "Default asset name failed; trying GitHub API redirect..."
        local api_url="https://api.github.com/repos/ImranR98/Obtainium/releases/tags/${version}"
        local asset_url
        asset_url=$(curl -sf "$api_url" \
            | python3 -c "import json,sys; r=json.load(sys.stdin); print([a['browser_download_url'] for a in r.get('assets',[]) if a['name'].endswith('.apk')][0])")
        [[ -n "$asset_url" ]] || die "No .apk asset found in release $version"
        curl -fL -o "$cache_path" "$asset_url" || die "Download failed: $asset_url"
    fi
    log_pass "Downloaded $(du -h "$cache_path" | cut -f1) to $cache_path"
    echo "$cache_path"
}

# Install the APK on the device
obtainium_install() {
    local apk="$1"
    log_info "Installing Obtainium APK on device..."
    adb install -r -t "$apk" >"$OI_TMP_DIR/adb_install.log" 2>&1 \
        || { cat "$OI_TMP_DIR/adb_install.log" >&2; die "adb install failed"; }
    log_pass "Obtainium installed"
}

# Top-level: download + install
obtainium_setup() {
    local apk
    apk=$(obtainium_fetch_apk "${OI_OBTAINIUM_VERSION:-}")
    obtainium_install "$apk"

    # Verify install
    local installed
    installed=$(adb shell pm list packages "$OI_OBTAINIUM_PKG" | tr -d '\r')
    if [[ "$installed" =~ ${OI_OBTAINIUM_PKG} ]]; then
        log_pass "Obtainium package present on device: $OI_OBTAINIUM_PKG"
    else
        die "Obtainium package missing after install: $OI_OBTAINIUM_PKG"
    fi
}
