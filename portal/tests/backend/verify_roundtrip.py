import sys
import os
import json

# Ensure portal root is in Python Path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(SCRIPT_DIR)
PORTAL_DIR = os.path.dirname(TESTS_DIR)
ROOT_DIR = os.path.dirname(PORTAL_DIR)

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

CONFIG_PATH = os.path.join(TESTS_DIR, 'config.test.json')
from backend.core import config
config.load_config_from_file(CONFIG_PATH)

from backend.core.database import get_session
from servers.obtainium_repo.models import App, Category, Setting
from servers.obtainium_repo.compiler import ObtainiumConfigCompiler
from servers.obtainium_repo.manager_cli import ObtainiumRepoManagerCLI
from backend.core import config

def canonicalize_app(app):
    # Normalize additionalSettings to a dict if it is a JSON string
    add_settings = app.get("additionalSettings", "{}")
    if isinstance(add_settings, str):
        try:
            add_settings = json.loads(add_settings)
        except Exception:
            add_settings = {"raw": add_settings}
    
    # Normalize categories by sorting them
    cats = sorted(app.get("categories", []))
    
    return {
        "id": app.get("id"),
        "name": app.get("name"),
        "url": app.get("url"),
        "overrideSource": app.get("overrideSource"),
        "preferredApkIndex": app.get("preferredApkIndex"),
        "pinned": app.get("pinned", False),
        "allowIdChange": app.get("allowIdChange", False),
        "categories": cats,
        "additionalSettings": add_settings
    }

def canonicalize_settings(settings):
    cats = settings.get("categories", "{}")
    if isinstance(cats, str):
        try:
            cats = json.loads(cats)
        except Exception:
            cats = {}
            
    normalized_settings = {k: v for k, v in settings.items() if k != "categories"}
    normalized_settings["categories"] = cats
    return normalized_settings

def run_verification():
    # 1. Load original export file
    export_path = os.path.join(PORTAL_DIR, 'tests', 'backend', 'baseline_obtainium-export.json')
    if not os.path.exists(export_path):
        print(f"Error: {export_path} not found.")
        sys.exit(1)
        
    with open(export_path, 'r', encoding='utf-8') as f:
        original = json.load(f)
        
    # 2. Re-import it into the database using CLI manager
    session = get_session()
    # Clean database first to do a pure roundtrip test
    session.query(App).delete()
    session.query(Category).delete()
    session.query(Setting).delete()
    session.commit()
    
    compiler = ObtainiumConfigCompiler(config)
    cli_manager = ObtainiumRepoManagerCLI(config, compiler)
    
    # Import apps
    imported_apps_count = 0
    for app_data in original.get("apps", []):
        app_id = cli_manager.import_app_config(app_data, session)
        if app_id:
            imported_apps_count += 1
            
    # Import settings & categories safely (upsert)
    settings_data = original.get("settings", {})
    for k, v in settings_data.items():
        if k == "categories":
            parsed_cats = v
            if isinstance(v, str):
                try:
                    parsed_cats = json.loads(v)
                except Exception:
                    parsed_cats = {}
            for cat_name, cat_color in parsed_cats.items():
                cat = session.query(Category).filter_by(name=cat_name).first()
                if cat:
                    cat.color = cat_color
                else:
                    new_cat = Category(name=cat_name, color=cat_color)
                    session.add(new_cat)
        else:
            setting = session.query(Setting).filter_by(key=k).first()
            if setting:
                setting.value = v
            else:
                new_setting = Setting(key=k, value=v)
                session.add(new_setting)
            
    session.commit()
    print(f"Imported {imported_apps_count} apps and settings into a clean database.")
    
    # 3. Compile from the database
    # Mocking base_url as 'http://localhost:8000'
    compiled = compiler.compile_master("http://localhost:8000")
    session.close()
    
    # 4. Semantically compare
    # Normalize original apps
    orig_apps = sorted([canonicalize_app(a) for a in original.get("apps", [])], key=lambda x: x["id"])
    comp_apps = sorted([canonicalize_app(a) for a in compiled.get("apps", [])], key=lambda x: x["id"])
    
    # Compare apps count
    if len(orig_apps) != len(comp_apps):
        print(f"Mismatch in apps count: original={len(orig_apps)}, compiled={len(comp_apps)}")
        return False
        
    # Compare each app
    for a1, a2 in zip(orig_apps, comp_apps):
        if a1["id"] != a2["id"]:
            print(f"App ID mismatch: {a1['id']} vs {a2['id']}")
            return False
            
        for k in a1.keys():
            if a1[k] != a2[k]:
                # Note: URL and overrideSource can differ for apps with self-hosted APKs (local apks)
                # because compile_master dynamically overrides them.
                if k in ("url", "overrideSource", "additionalSettings") and "scrape-index.html" in str(a2["url"]):
                    print(f"App {a1['id']} difference (Expected dynamic override for self-hosted APK): {k} -> original={a1[k]} vs compiled={a2[k]}")
                    continue
                print(f"Mismatch in app {a1['id']} key '{k}':\n  orig={a1[k]}\n  comp={a2[k]}")
                return False
                
    # Compare settings
    orig_settings = canonicalize_settings(original.get("settings", {}))
    comp_settings = canonicalize_settings(compiled.get("settings", {}))
    
    # ignore lastCompletedBGCheckTime since it could be dynamically updated or not critical
    orig_settings.pop("lastCompletedBGCheckTime", None)
    comp_settings.pop("lastCompletedBGCheckTime", None)
    
    if orig_settings != comp_settings:
        print(f"Mismatch in settings:\n  orig={orig_settings}\n  comp={comp_settings}")
        return False
        
    print("Success: Round-trip import and export is semantically identical!")
    return True

if __name__ == '__main__':
    success = run_verification()
    sys.exit(0 if success else 1)
