#!/usr/bin/env bash
# emulator.sh - start and stop Android emulator (B1 local AVD or B2 docker)
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Detect best available mode
emulator_detect_mode() {
    if [[ -n "${OI_EMULATOR_MODE:-}" ]]; then
        case "$OI_EMULATOR_MODE" in
            local|docker) echo "$OI_EMULATOR_MODE"; return ;;
            auto) : ;;
            *) die "Unknown --emulator-mode: $OI_EMULATOR_MODE (expected auto|local|docker)" ;;
        esac
    fi

    # Prefer local if avdmanager + emulator + system-image present
    if command -v avdmanager >/dev/null 2>&1 && command -v emulator >/dev/null 2>&1 \
        && [[ -d "${ANDROID_HOME:-$ANDROID_SDK_ROOT}/system-images" ]]; then
        echo "local"; return
    fi
    # Fall back to docker
    if command -v docker >/dev/null 2>&1; then
        echo "docker"; return
    fi
    die "Neither local AVD (ANDROID_HOME + sdkmanager + emulator + system image) nor docker is available"
}

# Wait for device to be fully booted
emulator_wait_for_boot() {
    local serial="${1:-}"
    local timeout="${2:-300}"
    local adb_args=()
    [[ -n "$serial" ]] && adb_args+=( -s "$serial" )

    log_info "Waiting for device to come online..."
    adb "${adb_args[@]}" wait-for-device

    log_info "Waiting for boot to complete (timeout=${timeout}s)..."
    local elapsed=0
    while (( elapsed < timeout )); do
        local booted
        booted=$(adb "${adb_args[@]}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n ')
        if [[ "$booted" == "1" ]]; then
            log_pass "Boot complete"
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    die "Emulator boot timed out after ${timeout}s"
}

# Start local AVD
emulator_start_local() {
    local sdk="${ANDROID_HOME:-$ANDROID_SDK_ROOT}"
    [[ -d "$sdk" ]] || die "ANDROID_HOME (or ANDROID_SDK_ROOT) must be set to your Android SDK"

    local avd="$OI_AVD_NAME"
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64)  arch="x86_64" ;;
        aarch64) arch="arm64-v8a" ;;
        *) die "Unsupported arch: $arch" ;;
    esac

    local img_pkg="system-images;android-${OI_AVD_SDK};google_apis;${arch}"
    if ! ls "$sdk/system-images/" 2>/dev/null | grep -q "android-${OI_AVD_SDK}"; then
        log_info "System image not present; installing: $img_pkg"
        yes | "$sdk/cmdline-tools/latest/bin/sdkmanager" "$img_pkg" "platforms;android-${OI_AVD_SDK}" >/dev/null
    fi

    if ! "$sdk/cmdline-tools/latest/bin/avdmanager" list avd 2>/dev/null | grep -q "Name: ${avd}$"; then
        log_info "Creating AVD: $avd"
        echo "no" | "$sdk/cmdline-tools/latest/bin/avdmanager" create avd \
            --name "$avd" --package "$img_pkg" --device "pixel" >/dev/null
    fi

    log_info "Starting emulator: $avd (headless, swiftshader)"
    "$sdk/emulator/emulator" -avd "$avd" \
        -no-window -no-audio -no-boot-anim -no-snapshot \
        -gpu swiftshader_indirect \
        -accel auto \
        >"$OI_TMP_DIR/emulator.log" 2>&1 &
    echo $! >"$OI_TMP_DIR/emulator.pid"
    add_cleanup_hook "emulator_stop_local"

    emulator_wait_for_boot "" 600
}

emulator_stop_local() {
    if [[ "${OI_KEEP_EMULATOR:-0}" == "1" ]]; then
        log_info "OI_KEEP_EMULATOR=1: not stopping local emulator"
        return 0
    fi
    if [[ -f "$OI_TMP_DIR/emulator.pid" ]]; then
        local pid
        pid=$(cat "$OI_TMP_DIR/emulator.pid")
        kill "$pid" 2>/dev/null || true
        rm -f "$OI_TMP_DIR/emulator.pid"
    fi
    adb -s emulator-5554 emu kill 2>/dev/null || true
}

# Start docker-based emulator
emulator_start_docker() {
    require docker

    local image="budtmo/docker-android:emulator_14.0"
    log_info "Pulling docker image (this may take a while): $image"
    docker pull "$image" >/dev/null 2>&1 || log_warn "docker pull failed; continuing (image may exist locally)"

    log_info "Starting docker container with headless emulator"
    docker run --rm -d \
        --name "oi-emu-$$" \
        --device /dev/kvm \
        -p 5555:5555 \
        -e ANDROID_PLATFORM="${OI_AVD_SDK}" \
        -e ANDROID_EMULATOR_SDK="${OI_AVD_SDK}" \
        -e EMULATOR_GPU_MODE=swiftshader \
        "$image" >/dev/null
    echo "oi-emu-$$" >"$OI_TMP_DIR/docker_container"
    add_cleanup_hook "emulator_stop_docker"

    log_info "Waiting for container to be ready..."
    local elapsed=0
    while (( elapsed < 120 )); do
        if adb connect localhost:5555 2>/dev/null | grep -q "connected"; then
            emulator_wait_for_boot "localhost:5555" 600
            return 0
        fi
        sleep 3
        elapsed=$((elapsed + 3))
    done
    die "Docker emulator did not come online within 120s"
}

emulator_stop_docker() {
    if [[ "${OI_KEEP_EMULATOR:-0}" == "1" ]]; then
        log_info "OI_KEEP_EMULATOR=1: not stopping docker container"
        return 0
    fi
    if [[ -f "$OI_TMP_DIR/docker_container" ]]; then
        local name
        name=$(cat "$OI_TMP_DIR/docker_container")
        docker stop "$name" 2>/dev/null || true
        rm -f "$OI_TMP_DIR/docker_container"
    fi
    adb disconnect localhost:5555 2>/dev/null || true
}

# Top-level dispatch
emulator_start() {
    local mode
    mode=$(emulator_detect_mode)
    log_info "Emulator mode: $mode"
    case "$mode" in
        local)  emulator_start_local ;;
        docker) emulator_start_docker ;;
    esac
    echo "$mode" >"$OI_TMP_DIR/emulator_mode"
}
