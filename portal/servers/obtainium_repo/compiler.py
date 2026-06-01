import os
import json
from sqlalchemy.orm import selectinload
from backend.core.database import get_session
from .models import App, Category, Setting

class ObtainiumConfigCompiler:
    """
    Compiles database app configs and global settings into an Obtainium-compatible JSON structure.
    """
    def __init__(self, core_config):
        self.config = core_config

    def compile_master(self, base_url, session=None):
        """
        Loads all application configurations from the database,
        combining them with global configurations.
        """
        if session is not None:
            return self._compile_master_with_session(base_url, session)
        
        from backend.core.database import session_scope
        with session_scope() as session:
            return self._compile_master_with_session(base_url, session)

    def _compile_master_with_session(self, base_url, session):
        # Query all apps with their categories and apks preloaded
        db_apps = session.query(App).options(
            selectinload(App.categories),
            selectinload(App.apks)
        ).order_by(App.id).all()

        compiled_apps = []
        for app in db_apps:
            try:
                export_app = {
                    "id": app.id,
                    "name": app.name,
                    "url": app.url,
                    "overrideSource": app.override_source,
                    "preferredApkIndex": app.preferred_apk_index,
                    "pinned": app.pinned,
                    "categories": [c.name for c in app.categories],
                    "allowIdChange": app.allow_id_change,
                    "additionalSettings": app.additional_settings.copy() if app.additional_settings else {}
                }
                
                # If this app has self-hosted local APKs
                if app.apks:
                    export_app["url"] = f"{base_url}/scrape-index.html"
                    export_app["overrideSource"] = "HTML"
                    
                    # Generate regex filters dynamically
                    escaped_pkg = app.id.replace(".", r"\.")
                    escaped_name = app.name.replace(".", r"\.").replace(' ', '_')
                    apk_filter = f"^{escaped_name}_{escaped_pkg}_v.*\\.apk$"
                    version_regex = f"^{escaped_name}_{escaped_pkg}_v([^\\s_]+).*\\.apk$"
                    
                    additional_settings = export_app.get("additionalSettings", {})
                    if not isinstance(additional_settings, dict):
                        additional_settings = {}
                        
                    additional_settings.update({
                        "apkFilterRegEx": apk_filter,
                        "versionExtractionRegEx": version_regex,
                        "matchGroupToUse": 1
                    })
                    export_app["additionalSettings"] = additional_settings
                    
                    # Get latest version from apks list
                    latest_apk = sorted(app.apks, key=lambda x: x.id)[-1]
                    export_app["_version"] = latest_apk.version
                    export_app["_latest_apk_id"] = latest_apk.id
                    arch_str = f"_{latest_apk.architecture}" if latest_apk.architecture else ""
                    v_prefix = "" if (latest_apk.version.lower().startswith('v') or latest_apk.version.lower().startswith('r')) else "v"
                    export_app["_filename"] = f"{escaped_name}_{app.id}_{v_prefix}{latest_apk.version}{arch_str}.apk"
                
                # Stringify additionalSettings for Obtainium compatibility
                if "additionalSettings" in export_app and isinstance(export_app["additionalSettings"], dict):
                    export_app["additionalSettings"] = json.dumps(export_app["additionalSettings"], ensure_ascii=False)
                    
                compiled_apps.append(export_app)
            except Exception as e:
                print(f"Error compiling app config {app.id}: {e}")

        # Load global settings from database settings table
        export_settings = {}
        try:
            db_settings = session.query(Setting).all()
            for s in db_settings:
                export_settings[s.key] = s.value
                
            # Load categories from categories table
            db_cats = session.query(Category).all()
            if db_cats:
                categories_dict = {c.name: c.color for c in db_cats}
                # Stringify categories for Obtainium compatibility
                export_settings["categories"] = json.dumps(categories_dict, ensure_ascii=False)
        except Exception as e:
            print(f"Error formulating export settings: {e}")

        master_export = {
            "version": 1,
            "apps": compiled_apps
        }
        if export_settings:
            master_export["settings"] = export_settings
            
        return master_export


