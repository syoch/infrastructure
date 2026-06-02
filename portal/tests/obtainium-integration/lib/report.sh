#!/usr/bin/env bash
# report.sh - collect per-app results and emit JSON + text reports
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Initialize the report; creates <output-dir> and report.json scaffold
report_init() {
    local out_dir="$1"
    local backup="$2"
    local emu_mode="$3"
    local obtainium_ver="$4"
    OI_REPORT_DIR="$out_dir"
    mkdir -p "$out_dir"
    OI_REPORT_JSON="$out_dir/report.json"
    OI_REPORT_TXT="$out_dir/report.txt"

    local started
    started=$(date -Iseconds)
    OI_REPORT_STARTED="$started"

    python3 - "$OI_REPORT_JSON" "$backup" "$emu_mode" "$obtainium_ver" "$started" <<'PY'
import json, sys
out_path, backup, emu_mode, obtainium_ver, started = sys.argv[1:]
report = {
    "summary": {
        "total": 0,
        "imported": 0,
        "downloaded": 0,
        "failed_import": 0,
        "failed_download": 0,
        "skipped": 0,
        "duration_seconds": 0,
    },
    "config": {
        "backup_tarball": backup,
        "emulator_mode": emu_mode,
        "obtainium_version": obtainium_ver,
        "started_at": started,
    },
    "apps": [],
}
with open(out_path, "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
PY
    log_info "Report initialized: $OI_REPORT_JSON"
}

# Append a per-app record. Args: id name url source is_self_hosted
# import_status download_status duration apk_path error_message
report_add_app() {
    local id="$1" name="$2" url="$3" source="$4" is_self_hosted="$5"
    local import_status="$6" download_status="$7"
    local duration="$8" apk_path="$9" error_message="${10:-}"

    python3 - "$OI_REPORT_JSON" "$id" "$name" "$url" "$source" "$is_self_hosted" \
        "$import_status" "$download_status" "$duration" "$apk_path" "$error_message" <<'PY'
import json, sys
p = sys.argv[1]
args = sys.argv[2:]
with open(p) as f:
    rep = json.load(f)
rep["apps"].append({
    "id": args[0],
    "name": args[1],
    "url": args[2],
    "source": args[3],
    "is_self_hosted": args[4] == "yes",
    "import_status": args[5],
    "download_status": args[6],
    "duration_seconds": int(args[7]) if args[7] else 0,
    "apk_path": args[8] or None,
    "error_message": args[9] or None,
})
totals = {
    "imported": sum(1 for a in rep["apps"] if a["import_status"] == "success"),
    "downloaded": sum(1 for a in rep["apps"] if a["download_status"] == "success"),
    "failed_import": sum(1 for a in rep["apps"] if a["import_status"] == "failed"),
    "failed_download": sum(1 for a in rep["apps"]
                           if a["import_status"] == "success" and a["download_status"] == "failed"),
    "skipped": sum(1 for a in rep["apps"] if a["import_status"] == "skipped"),
}
rep["summary"].update(totals, total=len(rep["apps"]))
with open(p, "w") as f:
    json.dump(rep, f, indent=2, ensure_ascii=False)
PY

    # Streaming text output
    local marker
    case "$import_status:$download_status" in
        success:success) marker="PASS" ;;
        success:skipped) marker="SKIP" ;;
        success:*)        marker="IMPORT_OK" ;;  # import OK, download failed
        skipped:*)        marker="SKIP" ;;
        *)                marker="FAIL" ;;
    esac
    local dur_s="$duration"
    printf '[%s] %s (%s) - %ss' "$marker" "$name" "$id" "$dur_s" >>"$OI_REPORT_TXT"
    if [[ -n "$error_message" ]]; then
        printf '\n       %s' "$error_message" >>"$OI_REPORT_TXT"
    fi
    printf '\n' >>"$OI_REPORT_TXT"
}

# Finalize the report: compute total duration, write summary
report_finalize() {
    local ended
    ended=$(date -Iseconds)
    local started_epoch
    started_epoch=$(date -d "$OI_REPORT_STARTED" +%s 2>/dev/null || echo 0)
    local ended_epoch
    ended_epoch=$(date -d "$ended" +%s)
    local dur=$((ended_epoch - started_epoch))

    python3 - "$OI_REPORT_JSON" "$dur" "$ended" <<'PY'
import json, sys
p, dur, ended = sys.argv[1], int(sys.argv[2]), sys.argv[3]
with open(p) as f:
    rep = json.load(f)
rep["summary"]["duration_seconds"] = dur
rep["config"]["ended_at"] = ended
with open(p, "w") as f:
    json.dump(rep, f, indent=2, ensure_ascii=False)
PY

    # Prepend summary header to the text report
    local summary
    summary=$(python3 -c "
import json
r = json.load(open('$OI_REPORT_JSON'))
s = r['summary']
print(f\"\"\"Obtainium Integration Report
============================
Backup:        {r['config']['backup_tarball']}
Emulator mode: {r['config']['emulator_mode']}
Obtainium:     {r['config']['obtainium_version']}
Started:       {r['config']['started_at']}
Ended:         {r['config']['ended_at']}

Summary: {s['total']} apps / {s['imported']} imported / {s['downloaded']} downloaded / {s['failed_import']} import failures / {s['failed_download']} download failures / {s['skipped']} skipped / {s['duration_seconds']}s
\"\"\")
")
    {
        echo "$summary"
        cat "$OI_REPORT_TXT"
    } >"$OI_TMP_DIR/report.tmp"
    mv "$OI_TMP_DIR/report.tmp" "$OI_REPORT_TXT"

    log_pass "Report written: $OI_REPORT_JSON"
    log_pass "Report written: $OI_REPORT_TXT"
    echo
    cat "$OI_REPORT_TXT"
}

# Print the summary line to stderr (for live progress)
report_running_summary() {
    python3 - "$OI_REPORT_JSON" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
s = r['summary']
done = s['imported'] + s['failed_import'] + s['skipped']
print(f"  Progress: {done}/{s['total']} apps (imported={s['imported']}, failed={s['failed_import']}, skipped={s['skipped']}, downloaded={s['downloaded']})")
PY
}
