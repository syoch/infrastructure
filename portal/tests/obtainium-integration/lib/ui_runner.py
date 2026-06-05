#!/usr/bin/env python3
import subprocess
import xml.etree.ElementTree as ET
import time
import re
import sys
import os

class Automator:
    def __init__(self, debug=False):
        self.debug = debug

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
            # Strip out any non-XML preamble if adb outputs it
            start = out.find("<?xml")
            if start != -1:
                out = out[start:]
            return ET.fromstring(out)
        except Exception as e:
            self.log(f"dump failed: {e}")
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

    def wait_and_tap(self, pattern, timeout=10.0, poll_interval=0.2):
        start = time.time()
        while time.time() - start < timeout:
            tree = self.dump()
            nodes = self.find_nodes(tree, text_pattern=pattern, desc_pattern=pattern)
            if nodes:
                nodes.sort(key=lambda n: n['area'])
                n = nodes[0]
                self.tap(n['cx'], n['cy'])
                return True
            time.sleep(poll_interval)
        return False
        
    def dismiss_dialogs(self):
        """Check for and dismiss known interrupting dialogs. Returns True if something was dismissed."""
        tree = self.dump()
        if tree is None: return False
        
        nodes = self.find_nodes(tree, text_pattern=r'^(OK|Ok|Okay|Allow|Allow access|Allow from this source|Got it|I understand|Acknowledged|Don.t allow|Navigate up|Back)$', desc_pattern=r'^(OK|Ok|Okay|Allow|Allow access|Allow from this source|Got it|I understand|Acknowledged|Don.t allow|Navigate up|Back)$')
        # Only click if we see evidence of a dialog
        indicators = self.find_nodes(tree, text_pattern=r'(Welcome|Allow Obtainium|send you notifications|Google Play Protect|2026|Verification|keepandroidopen|Note|Google verification|Install unknown apps|Your phone and personal data|More vulnerable|Some errors occurred|Could not find|suitable release|errors occurred)', desc_pattern=r'(Welcome|Allow Obtainium|send you notifications|Google Play Protect|2026|Verification|keepandroidopen|Note|Google verification|Install unknown apps|Your phone and personal data|More vulnerable|Some errors occurred|Could not find|suitable release|errors occurred)')
        
        if indicators and nodes:
            # Sort to click smallest button-like thing
            nodes.sort(key=lambda n: n['area'])
            self.log(f"Dismissing dialog. Indicator: {indicators[0]['text'] or indicators[0]['desc']} Button: {nodes[0]['text'] or nodes[0]['desc']}")
            self.tap(nodes[0]['cx'], nodes[0]['cy'])
            return True
            
        # Check special toggle case for unknown sources
        toggles = self.find_nodes(tree, text_pattern=r'Allow from this source|Install unknown apps')
        if toggles:
            allow_nodes = self.find_nodes(tree, text_pattern='Allow from this source')
            if allow_nodes:
                self.tap(allow_nodes[0]['cx'], allow_nodes[0]['cy'])
                time.sleep(0.5)
            # Find navigate up
            nav_up = self.find_nodes(tree, desc_pattern='Navigate up')
            if nav_up:
                self.tap(nav_up[0]['cx'], nav_up[0]['cy'])
            else:
                subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"])
            return True
            
        return False

if __name__ == "__main__":
    a = Automator(debug=True)
    tree = a.dump()
    print(f"Nodes found: {len(a.find_nodes(tree))}")
