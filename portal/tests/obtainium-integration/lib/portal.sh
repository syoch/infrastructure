#!/usr/bin/env bash
# portal.sh - start a temporary portal instance for integration testing
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Find the infrastructure repo root (where portal/ lives)
portal_locate_repo() {
    local dir="$OI_ROOT"
    while [[ "$dir" != "/" ]]; do
        if [[ -d "$dir/portal" ]] && [[ -f "$dir/portal/manage.py" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    die "Could not locate infrastructure repo root (looked for portal/manage.py upward from $OI_ROOT)"
}

# Create a test config that uses an isolated sqlite database
portal_prepare_config() {
    local repo="$1"
    local tarball="$2"
    local cfg_dir="$OI_TMP_DIR/portal"
    mkdir -p "$cfg_dir/uploads"
    cat >"$cfg_dir/config.test.json" <<EOF
{
  "database": {
    "url": "sqlite:///${cfg_dir}/portal_integration.db",
    "sqlite_wal": true
  },
  "server": {
    "port": ${OI_PORTAL_PORT},
    "host": "127.0.0.1"
  },
  "extensions": [
    {
      "module": "servers.storage_manager",
      "class": "StorageManagerExtension",
      "config": {
        "uploads_dir": "${cfg_dir}/uploads"
      }
    },
    {
      "module": "servers.obtainium_repo",
      "class": "ObtainiumRepoExtension"
    }
  ]
}
EOF
    echo "$cfg_dir/config.test.json"
}

# Restore backup into the test database
portal_restore_backup() {
    local repo="$1"
    local cfg="$2"
    local tarball="$3"

    [[ -f "$tarball" ]] || die "Backup tarball not found: $tarball"

    log_info "Restoring backup into test database: $tarball"
    ( cd "$repo" && python3 portal/manage.py --config "$cfg" restore --in "$tarball" ) \
        >>"$OI_TMP_DIR/portal.log" 2>&1 \
        || { tail -30 "$OI_TMP_DIR/portal.log" >&2; die "Restore failed (see $OI_TMP_DIR/portal.log)"; }
    log_pass "Backup restored"
}

# Start the portal as a background process
portal_start_server() {
    local repo="$1"
    local cfg="$2"

    log_info "Starting portal on port ${OI_PORTAL_PORT} (background)"
    (
        cd "$repo"
        exec python3 portal/backend/main.py --config "$cfg"
    ) >>"$OI_TMP_DIR/portal.log" 2>&1 &
    echo $! >"$OI_TMP_DIR/portal.pid"
    add_cleanup_hook "portal_stop_server"

    # Wait for portal to respond
    local elapsed=0
    while (( elapsed < 60 )); do
        if curl -sf "http://127.0.0.1:${OI_PORTAL_PORT}/api/settings" >/dev/null 2>&1; then
            log_pass "Portal is up (pid=$(cat "$OI_TMP_DIR/portal.pid"))"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    tail -30 "$OI_TMP_DIR/portal.log" >&2
    die "Portal did not respond within 60s"
}

portal_stop_server() {
    if [[ -f "$OI_TMP_DIR/portal.pid" ]]; then
        local pid
        pid=$(cat "$OI_TMP_DIR/portal.pid")
        kill "$pid" 2>/dev/null || true
        rm -f "$OI_TMP_DIR/portal.pid"
    fi
}

# Make the host portal reachable from the device
portal_adb_reverse() {
    log_info "adb reverse tcp:${OI_PORTAL_PORT} tcp:${OI_PORTAL_PORT}"
    adb reverse "tcp:${OI_PORTAL_PORT}" "tcp:${OI_PORTAL_PORT}" >/dev/null
    add_cleanup_hook "portal_adb_unreverse"
}

portal_adb_unreverse() {
    adb reverse --remove "tcp:${OI_PORTAL_PORT}" 2>/dev/null || true
}

# Fetch /obtainium-export.json from the running portal
portal_fetch_export() {
    local out="$1"
    local url="http://127.0.0.1:${OI_PORTAL_PORT}/obtainium-export.json"
    log_info "Fetching export: $url"
    if ! curl -sf "$url" -o "$out"; then
        die "Failed to fetch $url"
    fi
    local count
    count=$(python3 -c "import json,sys; d=json.load(open('$out')); print(len(d.get('apps',[])))")
    log_pass "Export contains $count apps"
    echo "$count"
}

# Top-level: start a test portal and produce export.json
portal_start() {
    local tarball="$1"
    local export_path="$2"

    local repo
    repo=$(portal_locate_repo)

    local cfg
    cfg=$(portal_prepare_config "$repo" "$tarball")

    portal_restore_backup "$repo" "$cfg" "$tarball"
    portal_start_server "$repo" "$cfg"
    portal_adb_reverse
    portal_fetch_export "$export_path" >/dev/null

    # Write the device-reachable URL for self-hosted apps
    cat >"$OI_TMP_DIR/portal_device_url" <<EOF
http://127.0.0.1:${OI_PORTAL_PORT}
EOF
    log_info "Device-reachable portal URL: $(cat $OI_TMP_DIR/portal_device_url)"
}

portal_stop() {
    portal_stop_server
    portal_adb_unreverse
}
