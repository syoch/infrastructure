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
        self.last_dump_time = 0

    def log(self, msg):
        if self.debug:
            print(f"[DEBUG] {msg}", file=sys.stderr)

    def dump(self):
        """Fetch UI dump directly from stdout, very fast (~100ms)"""
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
            self.last_dump_time = time.time()
            return ET.fromstring(out)
        except Exception as e:
            # Sometimes dump fails if UI is busy
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

    def dismiss_dialogs(self, tree):
        """Check for and dismiss known interrupting dialogs (permissions, welcome, errors)."""
        nodes = self.find_nodes(tree, text_pattern=r'^(OK|Ok|Okay|Allow|Allow access|Allow from this source|Got it|I understand|Acknowledged|Don.t allow|Navigate up|Back)$', desc_pattern=r'^(OK|Ok|Okay|Allow|Allow access|Allow from this source|Got it|I understand|Acknowledged|Don.t allow|Navigate up|Back)$')
        indicators = self.find_nodes(tree, text_pattern=r'(Welcome|Allow Obtainium|send you notifications|Google Play Protect|2026|Verification|keepandroidopen|Note|Google verification|Install unknown apps|Your phone and personal data|More vulnerable|Some errors occurred|Could not find|suitable release|errors occurred)', desc_pattern=r'(Welcome|Allow Obtainium|send you notifications|Google Play Protect|2026|Verification|keepandroidopen|Note|Google verification|Install unknown apps|Your phone and personal data|More vulnerable|Some errors occurred|Could not find|suitable release|errors occurred)')
        
        if indicators and nodes:
            nodes.sort(key=lambda n: n['area'])
            self.log(f"Dismissing dialog. Button: {nodes[0]['text'] or nodes[0]['desc']}")
            self.tap(nodes[0]['cx'], nodes[0]['cy'])
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
                subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"])
            return True
            
        return False

def import_apps(export_json_path, portal_url, debug=False):
    a = Automator(debug=debug)
    
    with open(export_json_path) as f:
        export_data = json.load(f)
    
    apps = export_data.get("apps", [])
    total = len(apps)
    print(f"Fast importing {total} apps...")

    # Restart Obtainium to start fresh
    subprocess.run(["adb", "shell", "am", "force-stop", "dev.imranr.obtainium"])
    subprocess.run(["adb", "shell", "monkey", "-p", "dev.imranr.obtainium", "-c", "android.intent.category.LAUNCHER", "1"], stdout=subprocess.DEVNULL)
    time.sleep(2)

    for i, app in enumerate(apps):
        app_id = app.get("id")
        app_name = app.get("name", "?")
        print(f"[{i+1}/{total}] Importing {app_name} ({app_id})")

        # Send Deep Link
        encoded_json = urllib.parse.quote(json.dumps(app))
        deep_url = f"obtainium://app/{encoded_json}"
        subprocess.run(["adb", "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", deep_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # State machine for this app's import
        start_time = time.time()
        imported = False
        while time.time() - start_time < 30: # 30s timeout per app import
            tree = a.dump()
            if tree is None:
                time.sleep(0.1)
                continue

            # Check if import confirmation dialog is present
            continue_nodes = a.find_nodes(tree, text_pattern=r'^Continue$', desc_pattern=r'^Continue$')
            import_titles = a.find_nodes(tree, text_pattern=r'^Import app$', desc_pattern=r'^Import app$')
            
            if continue_nodes and import_titles:
                continue_nodes.sort(key=lambda n: n['area'])
                a.tap(continue_nodes[0]['cx'], continue_nodes[0]['cy'])
                print(f"  -> Tapped Continue")
                imported = True
                
                # Wait a tiny bit for the dialog to disappear, then clear potential error dialogs
                time.sleep(1)
                for _ in range(3):
                    t2 = a.dump()
                    if a.dismiss_dialogs(t2):
                        time.sleep(0.5)
                    else:
                        break
                break # Move to next app
            
            # If not import dialog, check if it's a known interrupting dialog and dismiss it
            if a.dismiss_dialogs(tree):
                time.sleep(0.2)
                continue

            # Wait briefly before polling again
            time.sleep(0.1)

        if not imported:
            print(f"  -> Timeout or failed to import")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: fast_import.py <export_json_path> <portal_url>")
        sys.exit(1)
    import_apps(sys.argv[1], sys.argv[2], debug=True)
