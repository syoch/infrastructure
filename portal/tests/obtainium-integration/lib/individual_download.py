#!/usr/bin/env python3
"""
Individual Download Test

Downloads apps one by one to verify URL generation and file hosting correctness.
For self-hosted apps: verifies portal download URLs via HTTP GET.
For all apps: imports into Obtainium and triggers individual downloads via UI.

This is a calibration/validation test that takes time but verifies each app
individually with clear per-app success/failure reporting.
"""
import subprocess
import xml.etree.ElementTree as ET
import time
import re
import sys
import json
import urllib.parse
import http.client
import ssl


class Automator:
    def __init__(self, debug=False):
        self.debug = debug

    def log(self, msg):
        if self.debug:
            print(f"[DEBUG] {msg}", file=sys.stderr, flush=True)

    def dump(self):
        try:
            res = subprocess.run(
                ["adb", "exec-out", "uiautomator", "dump", "/dev/tty"],
                capture_output=True, text=True, check=True
            )
            out = res.stdout
            if "UI hierchary dumped to" in out:
                out = out.split("UI hierchary dumped to", 1)[0]
            start = out.find("<?xml")
            if start != -1:
                out = out[start:]
            return ET.fromstring(out)
        except Exception:
            return None

    def find_nodes(self, tree, text_pattern=None, desc_pattern=None, class_name=None):
        if tree is None:
            return []
        matches = []
        for c in tree.iter():
            text = c.get("text", "") or ""
            desc = c.get("content-desc", "") or ""
            cls = c.get("class", "") or ""
            if class_name and cls != class_name:
                continue
            match = False
            if text_pattern and re.search(text_pattern, text, re.IGNORECASE):
                match = True
            if desc_pattern and re.search(desc_pattern, desc, re.IGNORECASE):
                match = True
            if match:
                b = c.get("bounds", "")
                m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    area = (x2 - x1) * (y2 - y1)
                    matches.append({'cx': cx, 'cy': cy, 'area': area,
                                    'text': text, 'desc': desc, 'bounds': b})
        return matches

    def tap(self, x, y):
        self.log(f"tapping {x}, {y}")
        subprocess.run(["adb", "shell", "input", "tap", str(x), str(y)], check=False)

    def back(self):
        subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"], check=False)



    def dismiss_dialogs(self, tree):
        update_nodes = self.find_nodes(tree, text_pattern=r'^Update$')
        install_nodes = self.find_nodes(tree, text_pattern=r'^Install$')
        do_you_want = self.find_nodes(tree, text_pattern=r'Do you want to (update|install)')
        if (update_nodes or install_nodes) and do_you_want:
            btn = update_nodes[0] if update_nodes else install_nodes[0]
            self.log(f"Tapping {btn['text']} on install confirmation")
            self.tap(btn['cx'], btn['cy'])
            return True

        toggles = self.find_nodes(tree, text_pattern=r'Allow from this source|Install unknown apps')
        if toggles:
            allow_nodes = self.find_nodes(tree, text_pattern='Allow from this source')
            if allow_nodes:
                self.tap(allow_nodes[0]['cx'], allow_nodes[0]['cy'])
                time.sleep(0.5)
            nav_up = self.find_nodes(tree, desc_pattern='Navigate up')
            if nav_up:
                self.tap(nav_up[0]['cx'], nav_up[0]['cy'])
            else:
                self.back()
            return True

        nodes = self.find_nodes(tree,
            text_pattern=r'^(OK|Ok|Okay|Allow|Allow access|Got it|I understand|Acknowledged|Don.t allow|Navigate up|Back|Use without an account|No thanks|Next|Accept|Agree|Done|Close|Dismiss)$',
            desc_pattern=r'^(OK|Ok|Okay|Allow|Allow access|Got it|I understand|Acknowledged|Don.t allow|Navigate up|Back|Use without an account|No thanks|Next|Accept|Agree|Done|Close|Dismiss)$')
        indicators = self.find_nodes(tree,
            text_pattern=r'(Welcome|Allow Obtainium|send you notifications|Google Play Protect|2026|Verification|Note|Some errors occurred|Could not find|suitable release|errors occurred|Welcome to Chrome|Add account|Chrome|first run|terms|privacy)',
            desc_pattern=r'(Welcome|Allow Obtainium|send you notifications|Google Play Protect|2026|Verification|Note|Some errors occurred|Could not find|suitable release|errors occurred|Welcome to Chrome|Add account|Chrome|first run|terms|privacy)')
        if indicators and nodes:
            nodes.sort(key=lambda n: n['area'])
            self.log(f"Dismissing dialog. Button: {nodes[0]['text'] or nodes[0]['desc']}")
            self.tap(nodes[0]['cx'], nodes[0]['cy'])
            return True
        return False




def verify_portal_url(app_id, url, portal_base):
    """Verify a self-hosted app's download URL via HTTP GET."""
    full_url = url.replace("http://127.0.0.1:18000", portal_base)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(full_url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=30)
        conn.request("GET", parsed.path)
        resp = conn.getresponse()
        if resp.status != 200:
            return False, f"HTTP {resp.status}"
        content_type = resp.getheader("Content-Type", "")
        content_length = int(resp.getheader("Content-Length", "0"))
        if content_length == 0:
            return False, "Empty response"
        # Read first 4 bytes to check APK magic (PK\x03\x04)
        data = resp.read(4)
        conn.close()
        if data[:2] != b'PK':
            return False, f"Not an APK (magic: {data[:4].hex()})"
        return True, f"OK ({content_length} bytes, {content_type})"
    except Exception as e:
        return False, str(e)


def verify_url_from_host(url, timeout=60):
    """Download APK URL from host side and verify. Follows redirects up to 5 hops."""
    if not url or url == "placeholder":
        return False, "Placeholder URL", 0
    try:
        from urllib.parse import urlparse
        import http.client
        current_url = url
        for _ in range(5):
            parsed = urlparse(current_url)
            if parsed.scheme == 'https':
                conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=timeout)
            else:
                conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=timeout)
            path = parsed.path
            if parsed.query:
                path += "?" + parsed.query
            conn.request("GET", path)
            resp = conn.getresponse()
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.getheader("Location")
                conn.close()
                if not location:
                    return False, f"Redirect without Location", 0
                if location.startswith("/"):
                    location = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}{location}"
                current_url = location
                continue
            if resp.status != 200:
                return False, f"HTTP {resp.status}", 0
            content_length = int(resp.getheader("Content-Length", "0"))
            data = resp.read(4)
            conn.close()
            if data[:2] != b'PK':
                return False, f"Not an APK (magic: {data[:4].hex()})", content_length
            return True, f"OK ({content_length} bytes)", content_length
        return False, "Too many redirects", 0
    except Exception as e:
        return False, str(e), 0


def read_app_data_from_device(app_id):
    """Read app JSON config from Obtainium's device storage."""
    res = subprocess.run(
        ["adb", "shell", f"cat /data/media/0/Android/data/dev.imranr.obtainium/files/app_data/{app_id}.json"],
        capture_output=True, text=True
    )
    if res.returncode != 0 or not res.stdout.strip():
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def run_part_c_non_ui(apps, report, report_json_path, portal_base="http://127.0.0.1:18000"):
    """Part C: Verify download URLs via HTTP (no UI needed, reads from device app_data)."""
    print(f"\n=== Part C: Non-UI Download Verification ({len(apps)} apps) ===")

    github_rate_limited = False

    for idx, app in enumerate(apps):
        app_id = app.get("id")
        app_name = app.get("name", "?")

        print(f"\n[{idx+1}/{len(apps)}] {app_name} ({app_id})")

        # Read apkUrls from device's app_data (populated by background check)
        data_res = subprocess.run(
            ["adb", "shell", f"cat /data/media/0/Android/data/dev.imranr.obtainium/files/app_data/{app_id}.json"],
            capture_output=True, text=True
        )
        if data_res.returncode != 0 or not data_res.stdout.strip():
            print(f"  -> No app data on device")
            _update_report(report, report_json_path, app_id, "failed", None,
                           "App data not found on device")
            continue

        try:
            device_data = json.loads(data_res.stdout)
        except json.JSONDecodeError:
            print(f"  -> Failed to parse app data")
            _update_report(report, report_json_path, app_id, "failed", None,
                           "Invalid app data JSON")
            continue

        apk_urls_raw = device_data.get("apkUrls", "[]")
        if isinstance(apk_urls_raw, str):
            try:
                apk_urls = json.loads(apk_urls_raw)
            except json.JSONDecodeError:
                print(f"  -> Failed to parse apkUrls: {apk_urls_raw[:100]}")
                _update_report(report, report_json_path, app_id, "failed", None,
                               "Invalid apkUrls format")
                continue
        else:
            apk_urls = apk_urls_raw

        if not apk_urls:
            print(f"  -> No apkUrls in app data")
            _update_report(report, report_json_path, app_id, "failed", None,
                           "No apkUrls in app data")
            continue

        # Filter out placeholder URLs
        real_urls = [(fn, url) for fn, url in apk_urls if url and url != "placeholder"]
        if not real_urls:
            print(f"  -> Only placeholder URLs (background check incomplete)")
            _update_report(report, report_json_path, app_id, "failed", None,
                           "Background check did not populate URLs")
            continue

        # Try each URL until one works
        success = False
        for filename, url in real_urls:
            # Replace 127.0.0.1:18000 with portal_base if needed
            if "127.0.0.1:18000" in url:
                url = url.replace("http://127.0.0.1:18000", portal_base)

            # Skip GitHub API if rate limited
            if github_rate_limited and "api.github.com" in url:
                print(f"  Skipping GitHub URL (rate limited): {filename}")
                continue

            print(f"  Trying: {filename} -> {url[:80]}...")
            start = time.time()
            ok, msg, size = verify_url_from_host(url, timeout=60)
            dur = int(time.time() - start)

            if ok:
                print(f"  -> SUCCESS: {msg} ({dur}s)")
                _update_report(report, report_json_path, app_id, "success", None, None, dur)
                success = True
                break
            else:
                print(f"  -> FAILED: {msg} ({dur}s)")
                if "403" in msg and "github" in url.lower():
                    github_rate_limited = True
                    print(f"  -> GitHub API rate limited, skipping remaining GitHub URLs")

        if not success:
            _update_report(report, report_json_path, app_id, "failed", None,
                           "All URLs failed verification")



def run_individual_download(apps_txt_path, report_json_path, portal_base="http://127.0.0.1:18000",
                            skip_download=False, timeout=300):
    a = Automator(debug=True)

    with open(apps_txt_path) as f:
        apps = [json.loads(line) for line in f if line.strip()]

    total = len(apps)
    print(f"=== Individual Download Test: {total} apps ===")

    with open(report_json_path) as f:
        report = json.load(f)

    # ========================================================================
    # Part A: Verify self-hosted app URLs via HTTP (fast, no emulator needed)
    # ========================================================================
    self_hosted = [app for app in apps if app.get("overrideSource") == "HTML"]
    external = [app for app in apps if app.get("overrideSource") != "HTML"]

    if self_hosted:
        print(f"\n=== Part A: Verifying {len(self_hosted)} self-hosted app URLs ===")
        for app in self_hosted:
            app_id = app.get("id")
            app_name = app.get("name", "?")
            apk_urls = app.get("apkUrls", "[]")
            if isinstance(apk_urls, str):
                apk_urls = json.loads(apk_urls)
            if not apk_urls:
                print(f"  [{app_id}] FAIL: No apkUrls in export")
                report["apps"].append({
                    "id": app_id, "name": app_name, "url": app.get("url", ""),
                    "source": "HTML", "is_self_hosted": True,
                    "import_status": "success", "download_status": "failed",
                    "duration_seconds": 0, "apk_path": None,
                    "error_message": "No apkUrls in export"
                })
                continue

            filename, download_url = apk_urls[0]
            start = time.time()
            ok, msg = verify_portal_url(app_id, download_url, portal_base)
            dur = int(time.time() - start)

            status = "success" if ok else "failed"
            print(f"  [{app_id}] {status}: {msg} ({dur}s)")

            report["apps"].append({
                "id": app_id, "name": app_name, "url": download_url,
                "source": "HTML", "is_self_hosted": True,
                "import_status": "success", "download_status": status,
                "duration_seconds": dur, "apk_path": None,
                "error_message": None if ok else msg
            })
            with open(report_json_path, "w") as f:
                json.dump(report, f, indent=2)

    if skip_download or not external:
        if not self_hosted:
            print("No self-hosted apps and skip_download set.")
        _finalize(report, report_json_path)
        return

    # ========================================================================
    # Part B: Import all apps via deep links
    # ========================================================================
    print(f"\n=== Part B: Importing {len(external)} apps ===")

    for i, app in enumerate(external):
        app_id = app.get("id")
        app_name = app.get("name", "?")

        app_url = app.get("url", "")
        if "portal.syoch.org" in app_url:
            app["url"] = re.sub(r'https?://portal\.syoch\.org', 'http://127.0.0.1:18000', app_url)

        print(f"[{i+1}/{len(external)}] Importing {app_name} ({app_id})")
        start_time = time.time()

        encoded_json = urllib.parse.quote(json.dumps(app))
        deep_url = f"obtainium://app/{encoded_json}"
        subprocess.run(["adb", "shell", "am", "start", "-a", "android.intent.action.VIEW",
                        "-d", deep_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        imported = False
        error_msg = None
        while time.time() - start_time < 30:
            tree = a.dump()
            if tree is None:
                time.sleep(0.1)
                continue
            continue_nodes = a.find_nodes(tree, text_pattern=r'^Continue$', desc_pattern=r'^Continue$')
            import_titles = a.find_nodes(tree, text_pattern=r'^Import app$', desc_pattern=r'^Import app$')
            if continue_nodes and import_titles:
                continue_nodes.sort(key=lambda n: n['area'])
                a.tap(continue_nodes[0]['cx'], continue_nodes[0]['cy'])
                print(f"  -> Tapped Continue")
                imported = True
                time.sleep(1)
                for _ in range(5):
                    t2 = a.dump()
                    if t2 is not None and a.dismiss_dialogs(t2):
                        time.sleep(0.5)
                    else:
                        break
                break
            if a.dismiss_dialogs(tree):
                time.sleep(0.2)
                continue
            time.sleep(0.1)

        dur = int(time.time() - start_time)
        if not imported:
            print(f"  -> Failed to import")
            error_msg = "Failed to import (timeout)"

        # Update or append to report
        existing = next((x for x in report["apps"] if x["id"] == app_id), None)
        if existing:
            existing["import_status"] = "success" if imported else "failed"
            existing["error_message"] = error_msg
        else:
            report["apps"].append({
                "id": app_id, "name": app_name, "url": app.get("url", ""),
                "source": app.get("overrideSource", "auto"), "is_self_hosted": False,
                "import_status": "success" if imported else "failed",
                "download_status": "skipped", "duration_seconds": dur,
                "apk_path": None, "error_message": error_msg
            })
        with open(report_json_path, "w") as f:
            json.dump(report, f, indent=2)

    # ========================================================================
    # Part B.5: Force background update check via SharedPreferences hack
    # ========================================================================
    print(f"\n=== Part B.5: Forcing background update check ===")
    _force_background_check(a)

    # ========================================================================
    # Part C: Non-UI Download Verification (read apkUrls from device, HTTP verify)
    # ========================================================================
    run_part_c_non_ui(external, report, report_json_path, portal_base)

    _finalize(report, report_json_path)


def _force_background_check(a):
    """Force Obtainium to run background update check via SharedPreferences hack."""
    import base64

    # Write SharedPreferences to enable background check on start
    new_prefs = """<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <boolean name="flutter.firstRun" value="false" />
    <boolean name="flutter.checkOnStart" value="true" />
    <boolean name="flutter.enableBackgroundUpdates" value="true" />
    <long name="flutter.lastCompletedBGCheckTime" value="0" />
</map>"""

    b64 = base64.b64encode(new_prefs.encode()).decode()
    subprocess.run(["adb", "shell",
                    f"echo {b64} | base64 -d > /data/data/dev.imranr.obtainium/shared_prefs/FlutterSharedPreferences.xml"],
                   check=True, capture_output=True)
    subprocess.run(["adb", "shell",
                    "chown u0_a192:u0_a192 /data/data/dev.imranr.obtainium/shared_prefs/FlutterSharedPreferences.xml"],
                   check=True, capture_output=True)
    print("  SharedPreferences written (checkOnStart=true, lastCompletedBGCheckTime=0)")

    # Restart Obtainium
    subprocess.run(["adb", "shell", "am", "force-stop", "dev.imranr.obtainium"], check=True)
    time.sleep(2)
    subprocess.run(["adb", "shell", "am", "start", "-S", "-n",
                    "dev.imranr.obtainium/dev.imranr.obtainium.MainActivity"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("  Obtainium restarted")

    # Poll for URL population (wait up to 120s)
    print("  Waiting for background check to populate URLs...")
    for i in range(24):
        time.sleep(5)
        # Check if any app has non-placeholder URLs
        res = subprocess.run(
            ["adb", "shell", "ls /data/media/0/Android/data/dev.imranr.obtainium/files/app_data/"],
            capture_output=True, text=True
        )
        files = [f.strip() for f in res.stdout.splitlines() if f.strip().endswith('.json')]
        if not files:
            print(f"  {(i+1)*5}s: No app data files yet...")
            continue

        populated = 0
        for f in files:
            data_res = subprocess.run(
                ["adb", "shell", f"cat /data/media/0/Android/data/dev.imranr.obtainium/files/app_data/{f}"],
                capture_output=True, text=True
            )
            if data_res.returncode == 0 and data_res.stdout.strip():
                try:
                    d = json.loads(data_res.stdout)
                    urls = d.get("apkUrls", "N/A")
                    if urls != '[["placeholder","placeholder"]]' and urls != "N/A":
                        populated += 1
                except json.JSONDecodeError:
                    pass

        print(f"  {(i+1)*5}s: {populated}/{len(files)} apps have URLs")
        if populated > 0:
            # Wait a bit more for remaining apps
            time.sleep(5)
            break

    print("  Background check complete")


def _update_report(report, report_json_path, app_id, status, apk_path=None,
                   error=None, duration=None):
    """Update report for a specific app."""
    for app in report["apps"]:
        if app["id"] == app_id:
            app["download_status"] = status
            app["apk_path"] = apk_path
            app["error_message"] = error
            if duration is not None:
                app["duration_seconds"] = duration
            break
    with open(report_json_path, "w") as f:
        json.dump(report, f, indent=2)


def _finalize(report, report_json_path):
    """Compute summary and write final report."""
    report["summary"]["total"] = len(report["apps"])
    report["summary"]["imported"] = sum(1 for a in report["apps"]
                                        if a.get("import_status") == "success")
    report["summary"]["downloaded"] = sum(1 for a in report["apps"]
                                          if a.get("download_status") == "success")
    report["summary"]["failed_import"] = sum(1 for a in report["apps"]
                                             if a.get("import_status") == "failed")
    report["summary"]["failed_download"] = sum(1 for a in report["apps"]
                                               if a.get("download_status") == "failed")
    report["summary"]["skipped"] = sum(1 for a in report["apps"]
                                       if a.get("download_status") == "skipped")
    with open(report_json_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n=== Summary ===")
    print(f"Total:      {report['summary']['total']}")
    print(f"Imported:   {report['summary']['imported']}")
    print(f"Downloaded: {report['summary']['downloaded']}")
    print(f"Failed:     {report['summary']['failed_import'] + report['summary']['failed_download']}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: individual_download.py <apps.txt> <report.json> [--skip-download] [--timeout N]")
        sys.exit(1)
    skip = "--skip-download" in sys.argv
    timeout = 300
    portal_base = "http://127.0.0.1:18000"
    for i, arg in enumerate(sys.argv):
        if arg == "--timeout" and i + 1 < len(sys.argv):
            try:
                timeout = int(sys.argv[i + 1])
            except ValueError:
                pass
        if arg == "--portal" and i + 1 < len(sys.argv):
            portal_base = sys.argv[i + 1]
    run_individual_download(sys.argv[1], sys.argv[2], portal_base=portal_base,
                            skip_download=skip, timeout=timeout)
