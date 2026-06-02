#!/usr/bin/env bash
# common.sh - shared utilities for obtainium-integration
# Source this file from other scripts.

set -o pipefail

# Colors (disable with NO_COLOR=1 or --no-color)
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
    C_RED=$'\033[0;31m'
    C_GREEN=$'\033[0;32m'
    C_YELLOW=$'\033[0;33m'
    C_BLUE=$'\033[0;34m'
    C_DIM=$'\033[2m'
    C_BOLD=$'\033[1m'
    C_RESET=$'\033[0m'
else
    C_RED="" C_GREEN="" C_YELLOW="" C_BLUE="" C_DIM="" C_BOLD="" C_RESET=""
fi

# Paths
export OI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export OI_LIB_DIR="$OI_ROOT/lib"
export OI_RESULTS_DIR="$OI_ROOT/results"
export OI_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/obtainium-integration"
export OI_TMP_DIR="${TMPDIR:-/tmp}/obtainium-integration-$$"
export OI_PORTAL_PORT="${OI_PORTAL_PORT:-18000}"
export OI_AVD_NAME="${OI_AVD_NAME:-oi_test_avd}"
export OI_AVD_SDK="${OI_AVD_SDK:-34}"
export OI_OBTAINIUM_PKG="dev.imranr.obtainium"

mkdir -p "$OI_CACHE_DIR" "$OI_RESULTS_DIR" "$OI_TMP_DIR"

# Logging
log_ts() { date '+%Y-%m-%d %H:%M:%S'; }

log_info()  { echo "${C_BLUE}[$(log_ts)] INFO${C_RESET}  $*" >&2; }
log_warn()  { echo "${C_YELLOW}[$(log_ts)] WARN${C_RESET}  $*" >&2; }
log_error() { echo "${C_RED}[$(log_ts)] ERROR${C_RESET} $*" >&2; }
log_debug() { [[ -n "${OI_DEBUG:-}" ]] && echo "${C_DIM}[$(log_ts)] DEBUG${C_RESET} $*" >&2; }
log_pass()  { echo "${C_GREEN}[$(log_ts)] PASS${C_RESET}  $*" >&2; }
log_fail()  { echo "${C_RED}[$(log_ts)] FAIL${C_RESET}  $*" >&2; }

die() {
    log_error "$*"
    exit 1
}

require() {
    local cmd="$1"
    command -v "$cmd" >/dev/null 2>&1 || die "Required command not found: $cmd"
}

# Cleanup trap target (set by main script)
oi_cleanup() {
    local rc=$?
    log_debug "Cleanup triggered (rc=$rc)"
    if [[ -n "${OI_CLEANUP_HOOKS:-}" ]]; then
        for hook in $OI_CLEANUP_HOOKS; do
            log_debug "Running cleanup hook: $hook"
            eval "$hook" || log_warn "Cleanup hook failed: $hook"
        done
    fi
    if [[ "${OI_KEEP_TMP:-0}" != "1" ]]; then
        rm -rf "$OI_TMP_DIR" 2>/dev/null || true
    fi
    exit $rc
}

trap_oi_cleanup() {
    trap oi_cleanup EXIT INT TERM
}

add_cleanup_hook() {
    OI_CLEANUP_HOOKS="${OI_CLEANUP_HOOKS:-} $1"
}
