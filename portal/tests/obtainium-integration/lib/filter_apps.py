#!/usr/bin/env python3
"""Emit a tab-separated list of app JSONs to stdout, with optional filters."""
import json
import sys
import re

export_path = sys.argv[1]
apps_limit = sys.argv[2] or ""
filter_re = sys.argv[3] or ""
skip_html = sys.argv[4] == "1"

with open(export_path) as f:
    data = json.load(f)

apps = data.get("apps", [])
count = 0
for app in apps:
    if skip_html and app.get("overrideSource") == "HTML":
        continue
    if filter_re:
        name = app.get("name", "") or ""
        aid = app.get("id", "") or ""
        if not (re.search(filter_re, name) or re.search(filter_re, aid)):
            continue
    print(json.dumps(app, ensure_ascii=False), end="\n")
    count += 1
    if apps_limit and count >= int(apps_limit):
        break
