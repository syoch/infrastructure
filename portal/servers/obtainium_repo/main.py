import os
import json
import urllib.parse
import time
from fastapi import APIRouter, Request, HTTPException, Query, Depends, File, UploadFile, Form
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import selectinload, Session
from backend.extensions.base import BaseExtension
from backend.utils.network import get_local_ip
from backend.core.database import get_db
from .models import App, Category, Setting, LocalAppAPK
from .compiler import ObtainiumConfigCompiler
from .manager_cli import ObtainiumRepoManagerCLI
from .utils import get_base_url

class AppSaveModel(BaseModel):
    id: str
    name: str
    url: str = ""
    overrideSource: str | None = None
    preferredApkIndex: int | None = None
    pinned: bool = False
    allowIdChange: bool = False
    categories: list[str] = []
    additionalSettings: dict = {}

class AppDeleteModel(BaseModel):
    id: str

# In-memory cache for compiled Obtainium export JSON
_export_cache = {}  # Map of base_url -> (compiled_dict, expiry_timestamp)
CACHE_TTL = 30.0    # seconds

def invalidate_export_cache():
    _export_cache.clear()

class ObtainiumRepoExtension(BaseExtension):
    """
    Obtainium Repository extension for the portal.
    Handles dynamic JSON generation, HTML scraping page generation, and APK file serving.
    """
    def __init__(self, core_config, ext_config=None):
        super().__init__(core_config)
        self.ext_config = ext_config or {}
        self.tags = ["index-compiler"]
        self.compiler = None
        self.cli_manager = None
        self.router = APIRouter()
        self.setup_routes()

    def setup(self):
        """Initializes dependencies for the extension."""
        provider_name = self.ext_config.get("storage_provider", "StorageManagerExtension")
        self.storage_ext = self.host.get_extension(provider_name, tags=["storage-provider"])
        
        self.compiler = ObtainiumConfigCompiler(self.config)
        self.cli_manager = ObtainiumRepoManagerCLI(self.config, self.compiler)

    def register_cli_commands(self, subparsers):
        """Registers CLI commands under the manage.py framework."""
        if not self.cli_manager:
            self.setup()
        self.cli_manager.register_commands(subparsers)

    def backup_data(self, session) -> dict:
        """Serializes App, Category, Setting, and LocalAppAPK records."""
        # 1. Categories
        categories = []
        for cat in session.query(Category).all():
            categories.append({
                "name": cat.name,
                "color": cat.color
            })

        # 2. Apps
        apps = []
        for app in session.query(App).all():
            apps.append({
                "id": app.id,
                "name": app.name,
                "url": app.url,
                "override_source": app.override_source,
                "preferred_apk_index": app.preferred_apk_index,
                "pinned": app.pinned,
                "allow_id_change": app.allow_id_change,
                "additional_settings": app.additional_settings,
                "categories": [c.name for c in app.categories]  # Many-to-Many
            })

        # 3. Settings
        settings = []
        for setting in session.query(Setting).all():
            settings.append({
                "key": setting.key,
                "value": setting.value
            })

        # 4. LocalAppAPKs
        local_apks = []
        for apk in session.query(LocalAppAPK).all():
            local_apks.append({
                "app_id": apk.app_id,
                "file_hash": apk.file_hash,
                "version": apk.version,
                "architecture": apk.architecture
            })

        return {
            "categories": categories,
            "apps": apps,
            "settings": settings,
            "local_app_apks": local_apks
        }

    def restore_data(self, session, data: dict, strategy: str):
        """Deserializes App, Category, Setting, and LocalAppAPK records."""
        # 1. Restore Categories
        print("Restoring Category records...")
        for cat_data in data.get("categories", []):
            cat = session.query(Category).filter_by(name=cat_data["name"]).first()
            if not cat:
                cat = Category(name=cat_data["name"], color=cat_data["color"])
                session.add(cat)
            else:
                cat.color = cat_data["color"]
        session.flush()

        # 2. Restore Apps
        print("Restoring App records...")
        for app_data in data.get("apps", []):
            # Extract categories array
            categories_list = app_data.pop("categories", [])
            
            # Rewrite Self-Hosted app source URL containing scrape-index.html to avoid hardcoded IP/port
            if app_data.get("override_source") == "HTML" and "scrape-index.html" in app_data.get("url", ""):
                print(f"Sanitizing Self-Hosted APK source URL for app {app_data.get('id')}: {app_data['url']} -> /scrape-index.html")
                app_data["url"] = "/scrape-index.html"

            app = session.query(App).filter_by(id=app_data["id"]).first()
            if not app:
                app = App(**app_data)
                session.add(app)
            else:
                app.name = app_data["name"]
                app.url = app_data["url"]
                app.override_source = app_data["override_source"]
                app.preferred_apk_index = app_data["preferred_apk_index"]
                app.pinned = app_data["pinned"]
                app.allow_id_change = app_data["allow_id_change"]
                app.additional_settings = app_data["additional_settings"]
            
            # Map Many-to-Many associations
            app.categories = []
            for cat_name in categories_list:
                cat = session.query(Category).filter_by(name=cat_name).first()
                if cat:
                    app.categories.append(cat)
        session.flush()

        # 3. Restore LocalAppAPKs
        print("Restoring LocalAppAPK records...")
        for apk_data in data.get("local_app_apks", []):
            existing = session.query(LocalAppAPK).filter_by(
                app_id=apk_data["app_id"],
                file_hash=apk_data["file_hash"],
                version=apk_data["version"],
                architecture=apk_data.get("architecture")
            ).first()
            if not existing:
                parent_app = session.query(App).filter_by(id=apk_data["app_id"]).first()
                if parent_app:
                    new_apk = LocalAppAPK(
                        app_id=apk_data["app_id"],
                        file_hash=apk_data["file_hash"],
                        version=apk_data["version"],
                        architecture=apk_data.get("architecture")
                    )
                    session.add(new_apk)
        session.flush()

        # 4. Restore Settings
        print("Restoring Setting records...")
        for setting_data in data.get("settings", []):
            setting = session.query(Setting).filter_by(key=setting_data["key"]).first()
            if not setting:
                setting = Setting(key=setting_data["key"], value=setting_data["value"])
                session.add(setting)
            else:
                setting.value = setting_data["value"]
        session.flush()

    def post_restore(self, strategy: str):
        """Hook called after successful database restoration."""
        invalidate_export_cache()

    def get_referenced_file_hashes(self, session) -> set:
        """Returns the set of file hashes currently referenced by registered LocalAppAPK records."""
        return {apk.file_hash for apk in session.query(LocalAppAPK).all()}

    def get_startup_info(self, local_ip: str) -> list:
        return [
            f"Obtainium Export: http://{local_ip}:{self.config.DEFAULT_PORT}/obtainium-export.json"
        ]

    def setup_routes(self):
        @self.router.get("/obtainium-export.json")
        def serve_export(request: Request, db: Session = Depends(get_db)):
            """Serves the dynamic, cached Obtainium configuration export JSON."""
            base_url = get_base_url(request, self.config.DEFAULT_PORT)

            now = time.time()
            if base_url in _export_cache:
                data, expiry = _export_cache[base_url]
                if now < expiry:
                    return data

            try:
                export_data = self.compiler.compile_master(base_url, session=db)
                _export_cache[base_url] = (export_data, now + CACHE_TTL)
                return export_data
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error compiling export JSON: {str(e)}")

        @self.router.get("/scrape-index.html", response_class=HTMLResponse)
        def serve_scrape_index(request: Request, db: Session = Depends(get_db)):
            """Serves the HTML scraping index where Obtainium detects local APKs."""
            base_url = get_base_url(request, self.config.DEFAULT_PORT)

            try:
                db_apks = db.query(LocalAppAPK).options(selectinload(LocalAppAPK.app)).all()
                
                html_lines = [
                    "<!DOCTYPE html>",
                    "<html>",
                    "<head>",
                    "  <title>Self-Hosted Obtainium Apps</title>",
                    "  <meta charset='utf-8'>",
                    "  <style>",
                    "    body { font-family: sans-serif; padding: 24px; background: #0f1015; color: #e1e3e6; }",
                    "    a { color: #00e5ff; text-decoration: none; }",
                    "    a:hover { text-decoration: underline; }",
                    "    li { margin: 8px 0; }",
                    "    .version { color: #8e94a0; font-family: monospace; margin-left: 8px; }",
                    "  </style>",
                    "</head>",
                    "<body>",
                    "  <h1>Self-Hosted Apps for Obtainium</h1>",
                    "  <p>Scraping index. Do not download directly.</p>",
                    "  <ul>"
                ]
                
                for apk in db_apks:
                    if not apk.app:
                        continue
                    app_name = apk.app.name
                    safe_name = "".join(c for c in app_name if c.isalnum() or c in (' ', '_', '-')).strip()
                    safe_name = safe_name.replace(' ', '_')
                    arch_str = f"_{apk.architecture}" if apk.architecture else ""
                    export_filename = f"{safe_name}_{apk.app_id}_v{apk.version}{arch_str}.apk"
                    
                    download_url = f"{base_url}/api/apps/download/{apk.id}"
                    html_lines.append(f'    <li>')
                    html_lines.append(f'      <a href="{download_url}">{export_filename}</a>')
                    html_lines.append(f'      <span class="version">{apk.version}</span>')
                    html_lines.append(f'    </li>')
                    
                html_lines.extend([
                    "  </ul>",
                    "</body>",
                    "</html>"
                ])
                
                return "\n".join(html_lines)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error generating scraping HTML: {str(e)}")

        @self.router.get("/api/apps/download/{apk_id}")
        def serve_download_apk(apk_id: int, db: Session = Depends(get_db)):
            """Streams the physical APK file from storage with dynamic filename renaming."""
            try:
                apk = db.query(LocalAppAPK).options(selectinload(LocalAppAPK.app)).filter_by(id=apk_id).first()
                if not apk:
                    raise HTTPException(status_code=404, detail=f"APK record not found for ID: {apk_id}")

                if not apk.app:
                    raise HTTPException(status_code=404, detail=f"App associated with APK ID {apk_id} does not exist.")

                # Resolve file path dynamically from storage extension
                storage_ext = self.storage_ext
                if not storage_ext:
                    raise HTTPException(status_code=500, detail="Storage provider is not initialized.")
                filepath = storage_ext.get_file_path(apk.file_hash)

                if not os.path.exists(filepath):
                    raise HTTPException(status_code=404, detail=f"APK file not found on disk: {apk.file_hash}.apk")

                # Formulate user-friendly download filename
                app_name = apk.app.name
                safe_name = "".join(c for c in app_name if c.isalnum() or c in (' ', '_', '-')).strip()
                safe_name = safe_name.replace(' ', '_')
                arch_str = f"_{apk.architecture}" if apk.architecture else ""
                export_filename = f"{safe_name}_{apk.app_id}_v{apk.version}{arch_str}.apk"

                # Standard RFC-compliant Content-Disposition header
                safe_filename_quoted = urllib.parse.quote(export_filename)
                headers = {
                    "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename_quoted}"
                }
                return FileResponse(
                    path=filepath,
                    media_type="application/vnd.android.package-archive",
                    headers=headers
                )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error serving download: {str(e)}")

        @self.router.get("/api/apps")
        def serve_apps_api(db: Session = Depends(get_db)):
            """API GET endpoint to retrieve list of all app configurations with categories and linked APKs."""
            try:
                db_apps = db.query(App).options(
                    selectinload(App.categories),
                    selectinload(App.apks)
                ).order_by(App.id).all()
                
                apps = []
                for app in db_apps:
                    apps.append({
                        "id": app.id,
                        "name": app.name,
                        "url": app.url,
                        "overrideSource": app.override_source,
                        "preferredApkIndex": app.preferred_apk_index,
                        "pinned": app.pinned,
                        "categories": [c.name for c in app.categories],
                        "allowIdChange": app.allow_id_change,
                        "additionalSettings": app.additional_settings if app.additional_settings else {},
                        "apks": [
                            {
                                "id": apk.id,
                                "version": apk.version,
                                "architecture": apk.architecture,
                                "file_hash": apk.file_hash
                            } for apk in app.apks
                        ]
                    })
                return {"apps": apps}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error reading app configurations: {str(e)}")

        @self.router.get("/api/settings")
        def serve_settings_api(db: Session = Depends(get_db)):
            """API GET endpoint to retrieve global settings configuration JSON from the database."""
            try:
                settings = {}
                db_settings = db.query(Setting).all()
                for s in db_settings:
                    settings[s.key] = s.value
                
                db_cats = db.query(Category).all()
                settings["categories"] = {c.name: c.color for c in db_cats}
                
                return settings
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error reading global settings: {str(e)}")

        @self.router.post("/api/apps/save")
        def handle_save_app(body: AppSaveModel, db: Session = Depends(get_db)):
            """API POST endpoint to save or update an app configuration in the database."""
            try:
                app = db.query(App).filter_by(id=body.id).first()
                if not app:
                    app = App(id=body.id)
                    db.add(app)
                
                app.name = body.name
                app.url = body.url
                app.override_source = body.overrideSource
                app.preferred_apk_index = body.preferredApkIndex
                app.pinned = body.pinned
                app.allow_id_change = body.allowIdChange
                app.additional_settings = body.additionalSettings
                
                categories = []
                for cat_name in body.categories:
                    cat = db.query(Category).filter_by(name=cat_name).first()
                    if not cat:
                        cat = Category(name=cat_name, color=4284857472)
                        db.add(cat)
                    categories.append(cat)
                app.categories = categories
                
                db.commit()
                invalidate_export_cache()
                return {"status": "success", "message": f"App '{body.id}' saved successfully."}
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Error saving app configuration: {str(e)}")

        @self.router.post("/api/apps/delete")
        def handle_delete_app(body: AppDeleteModel, db: Session = Depends(get_db)):
            """API POST endpoint to delete an app configuration from the database."""
            try:
                app = db.query(App).filter_by(id=body.id).first()
                if app:
                    file_hashes = [apk.file_hash for apk in app.apks]
                    db.delete(app)
                    db.commit()
                    invalidate_export_cache()
                    
                    for fh in file_hashes:
                        # Try to trigger CAS storage clean up via storage extension
                        storage_ext = self.storage_ext
                        if storage_ext:
                            try:
                                storage_ext.delete_file(fh)
                            except Exception as e:
                                print(f"Error triggering storage cleanup for {fh}: {e}")
                                    
                    return {"status": "success", "message": f"App '{body.id}' deleted."}
                else:
                    raise HTTPException(status_code=404, detail=f"App '{body.id}' not found")
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Error deleting app configuration: {str(e)}")

        @self.router.post("/api/apps/compile")
        def handle_compile(request: Request):
            """API POST endpoint to force cache invalidation and compilation."""
            try:
                invalidate_export_cache()
                
                base_url = get_base_url(request, self.config.DEFAULT_PORT)
                
                compiled_data = self.compiler.compile_master(base_url)
                
                return {
                    "status": "success", 
                    "message": "Cache invalidated and configuration compiled successfully.",
                    "count": len(compiled_data.get("apps", []))
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error during configuration compile: {str(e)}")

        @self.router.post("/api/settings/save")
        def handle_save_settings(data: dict, db: Session = Depends(get_db)):
            """API POST endpoint to save global settings in the database."""
            try:
                for k, v in data.items():
                    if k == "categories":
                        input_cats = v if isinstance(v, dict) else {}
                        
                        # Update/Add categories
                        for cat_name, cat_color in input_cats.items():
                            cat = db.query(Category).filter_by(name=cat_name).first()
                            if cat:
                                cat.color = cat_color
                            else:
                                new_cat = Category(name=cat_name, color=cat_color)
                                db.add(new_cat)
                                
                        # Delete categories not in input list
                        db_cats = db.query(Category).all()
                        for db_cat in db_cats:
                            if db_cat.name not in input_cats:
                                db.delete(db_cat)
                    else:
                        setting = db.query(Setting).filter_by(key=k).first()
                        if setting:
                            setting.value = v
                        else:
                            new_setting = Setting(key=k, value=v)
                            db.add(new_setting)
                            
                db.commit()
                invalidate_export_cache()
                return {"status": "success", "message": "Global settings saved."}
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Error saving global settings: {str(e)}")

        @self.router.post("/api/apps/local-apks")
        def handle_local_apk_upload(
            file: UploadFile = File(...),
            app_id: str = Form(...),
            version: str = Form(...),
            architecture: str = Form(None),
            db: Session = Depends(get_db)
        ):
            """POST /api/apps/local-apks - Atomic file upload and metadata registration."""
            try:
                file_content = file.file.read()
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {str(e)}")
            
            if not file_content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty.")

            app = db.query(App).filter_by(id=app_id).first()
            if not app:
                raise HTTPException(status_code=404, detail=f"Application '{app_id}' is not registered in the database.")

            arch = architecture
            if not arch or arch == "none" or arch == "auto":
                arch = None

            storage_ext = self.storage_ext
            if not storage_ext:
                raise HTTPException(status_code=500, detail="Storage provider is not initialized.")
            
            try:
                file_hash = storage_ext.save_file(file_content)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to save file to storage: {str(e)}")

            try:
                apk = db.query(LocalAppAPK).filter_by(
                    app_id=app_id,
                    version=version,
                    architecture=arch
                ).first()

                if apk:
                    old_hash = apk.file_hash
                    apk.file_hash = file_hash
                    db.commit()
                    if old_hash != file_hash:
                        try:
                            storage_ext.delete_file(old_hash)
                        except Exception:
                            pass
                else:
                    apk = LocalAppAPK(
                        app_id=app_id,
                        version=version,
                        architecture=arch,
                        file_hash=file_hash
                    )
                    db.add(apk)
                    db.commit()
                
                invalidate_export_cache()
                return {
                    "status": "success",
                    "message": "APK file and metadata registered successfully.",
                    "id": apk.id,
                    "file_hash": file_hash
                }
            except Exception as e:
                db.rollback()
                try:
                    storage_ext.delete_file(file_hash)
                except Exception as ex:
                    print(f"Error rolling back physical file write: {ex}")
                raise HTTPException(status_code=500, detail=f"Database error during registration: {str(e)}")

        @self.router.delete("/api/apps/local-apks/{apk_id}")
        def handle_delete_mapping(apk_id: int, db: Session = Depends(get_db)):
            """DELETE /api/apps/local-apks/{apk_id} - Removes APK metadata link from DB and triggers storage cleanup."""
            try:
                apk = db.query(LocalAppAPK).filter_by(id=apk_id).first()
                if apk:
                    file_hash = apk.file_hash
                    db.delete(apk)
                    db.commit()
                    invalidate_export_cache()
                    
                    # Try to trigger CAS storage clean up via storage extension if it is loaded
                    storage_ext = self.storage_ext
                    if storage_ext:
                        storage_ext.delete_file(file_hash)
                        
                    return {"status": "success", "message": "Local APK metadata mapping deleted successfully."}
                else:
                    raise HTTPException(status_code=404, detail=f"APK metadata ID '{apk_id}' not found")
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Error deleting APK metadata: {str(e)}")

        @self.router.post("/api/apps/import")
        def handle_import_settings(data: dict, db: Session = Depends(get_db)):
            """POST /api/apps/import - Imports an Obtainium export JSON into the database."""
            if not isinstance(data, dict) or ("apps" not in data and "settings" not in data):
                raise HTTPException(status_code=400, detail="JSON must contain 'apps' or 'settings' key")

            try:
                imported_count = 0
                for app in data.get("apps", []):
                    app_id = self.cli_manager.import_app_config(app, db)
                    if app_id:
                        imported_count += 1

                # Merge global settings & categories
                settings_data = data.get("settings")
                if settings_data:
                    for k, v in settings_data.items():
                        if k == "categories":
                            parsed_cats = v
                            if isinstance(v, str):
                                try:
                                    parsed_cats = json.loads(v)
                                except Exception:
                                    parsed_cats = {}
                            
                            for cat_name, cat_color in parsed_cats.items():
                                cat = db.query(Category).filter_by(name=cat_name).first()
                                if cat:
                                    cat.color = cat_color
                                else:
                                    new_cat = Category(name=cat_name, color=cat_color)
                                    db.add(new_cat)
                        else:
                            setting = db.query(Setting).filter_by(key=k).first()
                            if setting:
                                setting.value = v
                            else:
                                new_setting = Setting(key=k, value=v)
                                db.add(new_setting)

                db.commit()
                invalidate_export_cache()

                return {
                    "status": "success",
                    "message": f"Successfully imported {imported_count} apps and settings.",
                    "count": imported_count
                }
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Error importing configurations: {str(e)}")
