#!/usr/bin/env python3
import subprocess
import xml.etree.ElementTree as ET
import time
import re
import sys
import json
import urllib.parse
import os

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
        except Exception as e:
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
            if (not text_pattern and not desc_pattern) and (text or desc):
                match = True

            if match:
                b = c.get("bounds", "")
                m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    area = (x2 - x1) * (y2 - y1)
                    matches.append({'cx': cx, 'cy': cy, 'area': area, 'text': text, 'desc': desc, 'bounds': b})
        return matches

    def tap(self, x, y):
        self.log(f"tapping {x}, {y}")
        subprocess.run(["adb", "shell", "input", "tap", str(x), str(y)], check=False)

    def dump_retry(self, retries=3, delay=1):
        for _ in range(retries):
            t = self.dump()
            if t is not None:
                return t
            time.sleep(delay)
        return None

    def dismiss_dialogs(self, tree):
        # Handle system install confirmation ("Do you want to update/install?")
        update_nodes = self.find_nodes(tree, text_pattern=r'^Update$')
        install_nodes = self.find_nodes(tree, text_pattern=r'^Install$')
        do_you_want = self.find_nodes(tree, text_pattern=r'Do you want to (update|install)')
        if (update_nodes or install_nodes) and do_you_want:
            btn = update_nodes[0] if update_nodes else install_nodes[0]
            self.log(f"Tapping {btn['text']} on install confirmation")
            self.tap(btn['cx'], btn['cy'])
            return True

        # Handle "Install unknown apps" system settings page (check BEFORE general indicators)
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
                subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"])
            return True

        nodes = self.find_nodes(tree, text_pattern=r'^(OK|Ok|Okay|Allow|Allow access|Got it|I understand|Acknowledged|Don.t allow|Navigate up|Back|Use without an account)$', desc_pattern=r'^(OK|Ok|Okay|Allow|Allow access|Got it|I understand|Acknowledged|Don.t allow|Navigate up|Back|Use without an account)$')
        indicators = self.find_nodes(tree, text_pattern=r'(Welcome|Allow Obtainium|send you notifications|Google Play Protect|2026|Verification|keepandroidopen|Note|Google verification|Your phone and personal data|More vulnerable|Some errors occurred|Could not find|suitable release|errors occurred|Welcome to Chrome|Add account)', desc_pattern=r'(Welcome|Allow Obtainium|send you notifications|Google Play Protect|2026|Verification|keepandroidopen|Note|Google verification|Your phone and personal data|More vulnerable|Some errors occurred|Could not find|suitable release|errors occurred|Welcome to Chrome|Add account)')
        
        if indicators and nodes:
            nodes.sort(key=lambda n: n['area'])
            self.log(f"Dismissing dialog. Button: {nodes[0]['text'] or nodes[0]['desc']}")
            self.tap(nodes[0]['cx'], nodes[0]['cy'])
            return True
            
        return False

def run_test(apps_txt_path, report_json_path, skip_download=False, timeout=300):
    a = Automator(debug=True)
    
    with open(apps_txt_path) as f:
        apps = [json.loads(line) for line in f if line.strip()]
    
    total = len(apps)
    print(f"Starting fast import of {total} apps...")

    # Load existing report to update
    with open(report_json_path) as f:
        report = json.load(f)
    
    # Phase 1: Import
    for i, app in enumerate(apps):
        app_id = app.get("id")
        app_name = app.get("name", "?")
        
        # Rewrite self-hosted portal URLs to the emulator-reachable address
        app_url = app.get("url", "")
        if "portal.syoch.org" in app_url:
            app["url"] = re.sub(r'https?://portal\.syoch\.org', 'http://127.0.0.1:18000', app_url)
            
        print(f"[{i+1}/{total}] Importing {app_name} ({app_id})")

        start_time = time.time()
        
        # Send Deep Link
        encoded_json = urllib.parse.quote(json.dumps(app))
        deep_url = f"obtainium://app/{encoded_json}"
        subprocess.run(["adb", "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", deep_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
                
                # Wait to clear any post-import errors
                time.sleep(1)
                for _ in range(5):
                    t2 = a.dump()
                    if t2 and a.dismiss_dialogs(t2):
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
            error_msg = "Failed to import (timeout or error)"

        # Append to report immediately
        report["apps"].append({
            "id": app_id,
            "name": app_name,
            "url": app.get("url", ""),
            "source": app.get("overrideSource", "auto"),
            "is_self_hosted": False, # simplified
            "import_status": "success" if imported else "failed",
            "download_status": "skipped",
            "duration_seconds": dur,
            "apk_path": None,
            "error_message": error_msg
        })
        with open(report_json_path, "w") as f:
            json.dump(report, f, indent=2)

    if skip_download:
        print("Skipping bulk download phase.")
        return

    # Phase 2: Bulk Download
    print("=== Phase 2: Bulk Download ===")
    
    # Grant "Install unknown apps" permission proactively to avoid per-install dialogs
    subprocess.run(["adb", "shell", "appops", "set", "dev.imranr.obtainium", "REQUEST_INSTALL_PACKAGES", "allow"], check=False)
    subprocess.run(["adb", "shell", "appops", "set", "dev.imranr.obtainium", "MANAGE_EXTERNAL_STORAGE", "allow"], check=False)
    print("Granted install permissions")

    # Restart Obtainium and navigate to Apps tab
    subprocess.run(["adb", "shell", "am", "force-stop", "dev.imranr.obtainium"])
    time.sleep(1)
    subprocess.run(["adb", "shell", "am", "start", "-S", "-n", "dev.imranr.obtainium/dev.imranr.obtainium.MainActivity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)

    # Robustly dismiss ALL dialogs (Welcome, permissions, etc.)
    for _ in range(15):
        t = a.dump()
        if t is None:
            time.sleep(1)
            continue
        if not a.dismiss_dialogs(t):
            break
        time.sleep(1)

    # Bring Obtainium to foreground again (in case another app stole focus)
    subprocess.run(["adb", "shell", "am", "start", "-n", "dev.imranr.obtainium/dev.imranr.obtainium.MainActivity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)

    # Debug: dump screen to see what's showing
    t = a.dump_retry(retries=3, delay=1)
    if t is not None:
        descs = []
        texts = []
        for c in t.iter():
            d = c.get('content-desc', '') or ''
            tx = c.get('text', '') or ''
            b = c.get('bounds', '') or ''
            if d.strip(): descs.append(f"{d[:60]}@{b}")
            if tx.strip(): texts.append(f"{tx[:60]}@{b}")
        print(f"[DEBUG] Pre-navigate screen D={' | '.join(descs[:20])}")
        print(f"[DEBUG] Pre-navigate screen T={' | '.join(texts[:20])}")
    else:
        print("[DEBUG] Dump failed before tab navigation")

    # Navigate to Apps tab (Tab 1 of 4) - this is where the app list lives
    # Retry up to 5 times with increasing waits
    navigated = False
    for attempt in range(5):
        t = a.dump_retry(retries=2, delay=1)
        if t is None:
            print(f"[DEBUG] Dump failed (attempt {attempt+1}), waiting...")
            time.sleep(2)
            continue
        apps_tab = a.find_nodes(t, desc_pattern=r'Tab 1 of 4')
        if apps_tab:
            a.tap(apps_tab[0]['cx'], apps_tab[0]['cy'])
            time.sleep(2)
            print("Navigated to Apps tab")
            navigated = True
            break
        # Try finding by text "Apps"
        apps_tab = a.find_nodes(t, text_pattern=r'^Apps$')
        if apps_tab:
            a.tap(apps_tab[0]['cx'], apps_tab[0]['cy'])
            time.sleep(2)
            print("Navigated to Apps tab (by text)")
            navigated = True
            break
        # Try finding any node with "Tab 1" in desc
        apps_tab = a.find_nodes(t, desc_pattern=r'Tab 1')
        if apps_tab:
            a.tap(apps_tab[0]['cx'], apps_tab[0]['cy'])
            time.sleep(2)
            print("Navigated to Apps tab (by Tab 1)")
            navigated = True
            break
        # Debug: dump screen on every failed attempt
        descs = []
        texts = []
        for c in t.iter():
            d = c.get('content-desc', '') or ''
            tx = c.get('text', '') or ''
            b = c.get('bounds', '') or ''
            if d.strip(): descs.append(f"{d[:50]}@{b}")
            if tx.strip(): texts.append(f"{tx[:50]}@{b}")
        print(f"[DEBUG] Tab nav attempt {attempt+1} failed. D={' | '.join(descs[:15])}")
        print(f"[DEBUG] Tab nav attempt {attempt+1} failed. T={' | '.join(texts[:15])}")
        print(f"[DEBUG] Apps tab not found (attempt {attempt+1}), waiting...")
        time.sleep(2)

    if not navigated:
        # Fallback: try tapping known coordinates for bottom tab bar
        # First ensure Obtainium is in foreground
        subprocess.run(["adb", "shell", "am", "start", "-n", "dev.imranr.obtainium/dev.imranr.obtainium.MainActivity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        t = a.dump_retry(retries=3, delay=1)
        if t is not None:
            # Check if Obtainium is in foreground
            obtainium_found = False
            for c in t.iter():
                d = c.get('content-desc', '') or ''
                tx = c.get('text', '') or ''
                if 'obtainium' in d.lower() or 'obtainium' in tx.lower() or 'tab' in d.lower():
                    obtainium_found = True
                    break
            if not obtainium_found:
                print("WARNING: Obtainium may not be in foreground, retrying start")
                subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"])
                time.sleep(1)
                subprocess.run(["adb", "shell", "am", "start", "-S", "-n", "dev.imranr.obtainium/dev.imranr.obtainium.MainActivity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(5)
        print("WARNING: Could not find Apps tab by text, trying fallback coordinates")
        a.tap(135, 1728)  # Known location for Tab 1
        time.sleep(3)
        # Dismiss any dialogs that appeared
        for _ in range(5):
            t = a.dump_retry(retries=2)
            if t and a.dismiss_dialogs(t):
                time.sleep(1)
            else:
                break

    # Dismiss any dialogs after tab switch
    for _ in range(3):
        t = a.dump()
        if t and a.dismiss_dialogs(t):
            time.sleep(0.5)

    # Note: Filter step removed. After import, all apps appear in the list.
    # Select All works without filtering.

    # Dismiss any dialogs after tab switch
    for _ in range(5):
        t = a.dump_retry(retries=2)
        if t and a.dismiss_dialogs(t):
            time.sleep(0.5)
        else:
            break

    # Dump screen state for debugging
    t = a.dump()
    if t:
        descs = []
        texts = []
        for c in t.iter():
            d = c.get('content-desc', '') or ''
            tx = c.get('text', '') or ''
            b = c.get('bounds', '') or ''
            if d.strip(): descs.append(f"{d[:50]}@{b}")
            if tx.strip(): texts.append(f"{tx[:50]}@{b}")
        print(f"[DEBUG] Screen before select-all: D={' | '.join(descs[:15])}")
        print(f"[DEBUG] Screen before select-all: T={' | '.join(texts[:15])}")

    # Tap "Select all" button at bottom-left of screen
    # This button is at bounds [24,1464][201,1584] on 1080x1920 devices
    # It shows the total count (e.g. "27") and tapping it selects all apps
    a.tap(112, 1524)
    time.sleep(3)

    # Find and tap "Install/update selected apps" button
    # Need up to 3 attempts (tap select-all, verify, tap install)
    install_btns = []
    for sel_attempt in range(3):
        t = a.dump_retry(retries=2, delay=1)
        if t is None:
            time.sleep(2)
            continue

        # Print debug screen info
        descs = []
        texts = []
        for c in t.iter():
            d = c.get('content-desc', '') or ''
            tx = c.get('text', '') or ''
            b = c.get('bounds', '') or ''
            if d.strip(): descs.append(f"{d[:50]}@{b}")
            if tx.strip(): texts.append(f"{tx[:50]}@{b}")
        print(f"[DEBUG] Screen before install: D={' | '.join(descs[:15])}")
        print(f"[DEBUG] Screen before install: T={' | '.join(texts[:15])}")

        # Check for selection counter
        for c in t.iter():
            b = c.get('bounds', '')
            m = re.match(r'\[24,1464\]\[(\d+),1584\]', b)
            if m:
                d = c.get('content-desc', '')
                if d.isdigit():
                    print(f"Selection counter: {d} apps selected")
                break

        install_btns = a.find_nodes(t, desc_pattern=r'^Install/update selected apps$')
        if install_btns:
            break

        # If not found, maybe need to tap select-all again
        print(f"[DEBUG] Install button not found (attempt {sel_attempt+1}), tapping select-all again")
        a.tap(112, 1524)
        time.sleep(3)

    if install_btns:
        a.tap(install_btns[0]['cx'], install_btns[0]['cy'])
        time.sleep(2)
        # Handle confirmation dialogs (may be multiple Continue taps needed)
        for _ in range(5):
            t = a.dump()
            if t:
                a.dismiss_dialogs(t)
                cont_btns = a.find_nodes(t, desc_pattern=r'^Continue$')
                if cont_btns:
                    a.tap(cont_btns[0]['cx'], cont_btns[0]['cy'])
                    print(f"Tapped Continue (confirmation)")
                    time.sleep(3)
                    # Check if there's STILL a Continue button (multiple confirmations)
                    t2 = a.dump()
                    if t2:
                        cont2 = a.find_nodes(t2, desc_pattern=r'^Continue$')
                        if cont2:
                            continue  # Loop to tap Continue again
                    print("Bulk install triggered")
                    break
                # Also dismiss any error dialogs that pop up during install
                err = a.find_nodes(t, text_pattern=r'(Some errors occurred|Could not find|suitable release)')
                if err:
                    a.dismiss_dialogs(t)
                    time.sleep(1)
    else:
        print("WARNING: 'Install/update selected apps' button not found")

    print("Waiting for APKs...")
    elapsed = 0
    last_count = -1
    stable_polls = 0
    unpinned = set()
    handled_pick = False
    errors_dialog_seen = False

    pkg = "dev.imranr.obtainium"
    while elapsed < timeout:
        # Handle Pick an APK dialog - may appear multiple times
        handled_this_round = True
        while handled_this_round:
            handled_this_round = False
            t = a.dump()
            if t is None:
                break
            pick_nodes = a.find_nodes(t, desc_pattern=r'^Pick an APK$')
            if not pick_nodes:
                break
            handled_pick = True
            # Find app name from content-desc
            for c in t.iter():
                d = c.get('content-desc', '')
                if 'has more than one package:' in d:
                    unpinned.add(d.replace(' has more than one package:', '').strip())
            # Find any apk node and tap it
            apk_nodes = [c for c in t.iter() if c.get('content-desc', '').endswith('.apk')]
            if apk_nodes:
                b = apk_nodes[0].get('bounds', '')
                m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', b)
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    a.tap((x1+x2)//2, (y1+y2)//2)
                    time.sleep(1)
                    # Tap Continue if it appears
                    ct = a.dump()
                    if ct:
                        cont_btns = a.find_nodes(ct, desc_pattern=r'^Continue$')
                        if cont_btns:
                            a.tap(cont_btns[0]['cx'], cont_btns[0]['cy'])
                    time.sleep(2)
                    handled_this_round = True

        # Check for "Some errors occurred" dialog — signals bulk download finished
        t = a.dump()
        if t:
            err_nodes = a.find_nodes(t, text_pattern=r'Some errors occurred')
            if err_nodes:
                errors_dialog_seen = True
                # Capture ALL text from the dialog before dismissing
                all_text = []
                for c in t.iter():
                    tx = c.get('text', '') or ''
                    d = c.get('content-desc', '') or ''
                    if tx.strip() and len(tx) > 3:
                        all_text.append(tx[:200])
                    if d.strip() and len(d) > 3:
                        all_text.append(d[:200])
                error_detail = ' | '.join(all_text[:10])
                print(f"[ERRORS] Obtainium dialog: {error_detail}")
                # Tap Okay to dismiss
                ok_btns = a.find_nodes(t, text_pattern=r'^Okay$|^OK$|^Ok$')
                if ok_btns:
                    a.tap(ok_btns[0]['cx'], ok_btns[0]['cy'])
                time.sleep(1)
                # After dismissing errors, downloads are done — break out
                break

            # Actively dismiss system install dialogs, permission dialogs, etc.
            dismissed_something = True
            while dismissed_something:
                dismissed_something = False
                if a.dismiss_dialogs(t):
                    time.sleep(1)
                    t = a.dump()
                    if t:
                        dismissed_something = True
                    else:
                        break

            # Re-check for errors after dismissing other dialogs
            if t:
                err_nodes = a.find_nodes(t, text_pattern=r'Some errors occurred')
                if err_nodes:
                    errors_dialog_seen = True
                    all_text = []
                    for c in t.iter():
                        tx = c.get('text', '') or ''
                        d = c.get('content-desc', '') or ''
                        if tx.strip() and len(tx) > 3: all_text.append(tx[:200])
                        if d.strip() and len(d) > 3: all_text.append(d[:200])
                    error_detail = ' | '.join(all_text[:10])
                    print(f"[ERRORS] Obtainium dialog: {error_detail}")
                    a.dismiss_dialogs(t)
                    time.sleep(1)
                    break

        # Count APKs
        res = subprocess.run(
            ["adb", "shell", f"find /data/media/0/Android/data/{pkg}/ -type f -name '*.apk' 2>/dev/null"],
            capture_output=True, text=True
        )
        apk_lines = list(set(l.strip() for l in res.stdout.splitlines() if l.strip().endswith('.apk')))
        count = len(apk_lines)

        if count > 0:
            if count == last_count:
                stable_polls += 1
            else:
                stable_polls = 0
            last_count = count
            print(f"APKs downloaded: {count} (stable: {stable_polls}, elapsed: {elapsed}s)")
            # Only exit on stability if we've been stable for a LONG time (5 min)
            # and haven't seen any errors yet — errors dialog means we're done
            if stable_polls >= 60 and elapsed >= 120:
                print("No new APKs for 5 minutes, assuming downloads complete")
                break
        else:
            stable_polls = 0

        time.sleep(5)
        elapsed += 5

    if not errors_dialog_seen:
        print(f"Download monitoring ended after {elapsed}s (timeout={timeout}s)")

    # Update report
    apks = {}
    for line in apk_lines:
        filename = os.path.basename(line)
        if '-' in filename:
            aid = filename.rsplit('-', 1)[0]
        else:
            aid = filename.rsplit('.', 1)[0]
        apks[aid] = line

    for app in report.get("apps", []):
        app_id = app.get("id")
        app_name = app.get("name", "")
        
        # Approximate matching for unpinned since we only have names
        if any(u in app_name for u in unpinned) or any(u in app_id for u in unpinned):
            app["download_status"] = "unpinned"
            app["error_message"] = "Pick an APK dialog appeared (unpinned)"
            continue
            
        if app_id in apks:
            app["download_status"] = "success"
            app["apk_path"] = apks[app_id]
            app["error_message"] = None
        else:
            if app.get("import_status") == "success":
                app["download_status"] = "failed"
                app["error_message"] = "APK not found in cache after bulk download"

    report["summary"]["total"] = len(report["apps"])
    report["summary"]["imported"] = sum(1 for a in report["apps"] if a.get("import_status") == "success")
    report["summary"]["downloaded"] = sum(1 for a in report["apps"] if a.get("download_status") == "success")
    report["summary"]["failed_import"] = sum(1 for a in report["apps"] if a.get("import_status") == "failed")
    report["summary"]["failed_download"] = sum(1 for a in report["apps"] if a.get("download_status") == "failed")
    report["summary"]["skipped"] = sum(1 for a in report["apps"] if a.get("download_status") == "skipped")
    report["summary"]["unpinned"] = sum(1 for a in report["apps"] if a.get("download_status") == "unpinned")

    with open(report_json_path, "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)
    skip = "--skip-download" in sys.argv
    timeout = 300
    for i, arg in enumerate(sys.argv):
        if arg == "--timeout" and i + 1 < len(sys.argv):
            try: timeout = int(sys.argv[i + 1])
            except: pass
    run_test(sys.argv[1], sys.argv[2], skip_download=skip, timeout=timeout)
