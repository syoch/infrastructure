"""HTTP routes for the Obtainium repository extension.

Extracted from the extension class so ``main.py`` stays focused on the
extension lifecycle (setup, backup/restore, CLI). ``build_router(ext)`` returns
an ``APIRouter`` whose handlers close over the extension instance.
"""
import json
import logging
import os
import time
import urllib.parse
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .main import ObtainiumRepoExtension

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from backend.core.database import get_db
from .models import App, Category, LocalAppAPK, Setting
from .utils import export_apk_filename, get_base_url

logger = logging.getLogger(__name__)

# In-memory cache for compiled Obtainium export JSON: base_url -> (dict, expiry)
_export_cache: dict[str, tuple[dict[str, Any], float]] = {}
CACHE_TTL = 30.0  # seconds


def invalidate_export_cache() -> None:
    _export_cache.clear()


class AppSaveModel(BaseModel):
    id: str
    name: str
    url: str = ""
    overrideSource: str | None = None
    preferredApkIndex: int | None = None
    pinned: bool = False
    allowIdChange: bool = False
    categories: list[str] = []
    additionalSettings: dict[str, Any] = {}


class AppDeleteModel(BaseModel):
    id: str


def build_router(ext: "ObtainiumRepoExtension") -> APIRouter:
    router = APIRouter()

    @router.get("/obtainium-export.json")
    def serve_export(request: Request, db: Session = Depends(get_db)) -> Any:
        """Serves the dynamic, cached Obtainium configuration export JSON."""
        base_url = get_base_url(request, ext.config.DEFAULT_PORT)

        now = time.time()
        cached = _export_cache.get(base_url)
        if cached and now < cached[1]:
            return cached[0]

        try:
            export_data = ext.compiler.compile_master(base_url, session=db)
            _export_cache[base_url] = (export_data, now + CACHE_TTL)
            return export_data
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            logger.exception("Error compiling export JSON")
            raise HTTPException(status_code=500, detail=f"Error compiling export JSON: {str(e)}")

    @router.get("/scrape-index.html", response_class=HTMLResponse)
    def serve_scrape_index(request: Request, db: Session = Depends(get_db)) -> str:
        """Serves the HTML scraping index where Obtainium detects local APKs."""
        base_url = get_base_url(request, ext.config.DEFAULT_PORT)

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
                "  <ul>",
            ]

            for apk in db_apks:
                if not apk.app:
                    continue
                export_filename = export_apk_filename(apk.app.name, apk.app_id, apk.version, apk.architecture)
                download_url = f"{base_url}/api/apps/download/{apk.id}/{export_filename}"
                html_lines.append("    <li>")
                html_lines.append(f'      <a href="{download_url}">{export_filename}</a>')
                html_lines.append(f'      <span class="version">{apk.version}</span>')
                html_lines.append("    </li>")

            html_lines.extend(["  </ul>", "</body>", "</html>"])
            return "\n".join(html_lines)
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            logger.exception("Error generating scraping HTML")
            raise HTTPException(status_code=500, detail=f"Error generating scraping HTML: {str(e)}")

    def _serve_download_impl(apk_id: int, db: Session) -> FileResponse:
        """Shared implementation for APK download."""
        apk = db.query(LocalAppAPK).options(selectinload(LocalAppAPK.app)).filter_by(id=apk_id).first()
        if not apk:
            raise HTTPException(status_code=404, detail=f"APK record not found for ID: {apk_id}")
        if not apk.app:
            raise HTTPException(status_code=404, detail=f"App associated with APK ID {apk_id} does not exist.")

        storage_ext = ext.storage_ext
        if not storage_ext:
            raise HTTPException(status_code=500, detail="Storage provider is not initialized.")
        filepath = storage_ext.get_file_path(apk.file_hash)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail=f"APK file not found on disk: {apk.file_hash}.apk")

        export_filename = export_apk_filename(apk.app.name, apk.app_id, apk.version, apk.architecture)
        safe_filename_quoted = urllib.parse.quote(export_filename)
        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename_quoted}"}
        return FileResponse(
            path=filepath,
            media_type="application/vnd.android.package-archive",
            headers=headers,
        )

    @router.get("/api/apps/download/{apk_id}/{filename}")
    def serve_download_apk_with_filename(apk_id: int, filename: str = "", db: Session = Depends(get_db)) -> FileResponse:
        """Streams APK file. URL includes filename for Obtainium HTML source provider matching."""
        try:
            return _serve_download_impl(apk_id, db)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            logger.exception("Error serving download with filename")
            raise HTTPException(status_code=500, detail=f"Error serving download: {str(e)}")

    @router.get("/api/apps/download/{apk_id}")
    def serve_download_apk(apk_id: int, db: Session = Depends(get_db)) -> FileResponse:
        """Streams APK file. Legacy route without filename in URL."""
        try:
            return _serve_download_impl(apk_id, db)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            logger.exception("Error serving download")
            raise HTTPException(status_code=500, detail=f"Error serving download: {str(e)}")

    @router.get("/api/apps")
    def serve_apps_api(db: Session = Depends(get_db)) -> dict[str, Any]:
        """API GET endpoint to retrieve list of all app configurations with categories and linked APKs."""
        try:
            db_apps = db.query(App).options(
                selectinload(App.categories),
                selectinload(App.apks),
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
                            "file_hash": apk.file_hash,
                        }
                        for apk in app.apks
                    ],
                })
            return {"apps": apps}
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            logger.exception("Error reading app configurations")
            raise HTTPException(status_code=500, detail=f"Error reading app configurations: {str(e)}")

    @router.get("/api/settings")
    def serve_settings_api(db: Session = Depends(get_db)) -> dict[str, Any]:
        """API GET endpoint to retrieve global settings configuration JSON from the database."""
        try:
            settings = {s.key: s.value for s in db.query(Setting).all()}
            settings["categories"] = {c.name: c.color for c in db.query(Category).all()}
            return settings
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            logger.exception("Error reading global settings")
            raise HTTPException(status_code=500, detail=f"Error reading global settings: {str(e)}")

    @router.post("/api/apps/save")
    def handle_save_app(body: AppSaveModel, db: Session = Depends(get_db)) -> dict[str, Any]:
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
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            db.rollback()
            logger.exception("Error saving app configuration: %s", body.id)
            raise HTTPException(status_code=500, detail=f"Error saving app configuration: {str(e)}")

    @router.post("/api/apps/delete")
    def handle_delete_app(body: AppDeleteModel, db: Session = Depends(get_db)) -> dict[str, Any]:
        """API POST endpoint to delete an app configuration from the database."""
        try:
            app = db.query(App).filter_by(id=body.id).first()
            if not app:
                raise HTTPException(status_code=404, detail=f"App '{body.id}' not found")

            file_hashes = [apk.file_hash for apk in app.apks]
            db.delete(app)
            db.commit()
            invalidate_export_cache()

            storage_ext = ext.storage_ext
            if storage_ext:
                for fh in file_hashes:
                    try:
                        storage_ext.delete_file(fh)
                    except Exception as e:  # noqa: BLE001 - best-effort cleanup
                        logger.error("Error triggering storage cleanup for %s: %s", fh, e)

            return {"status": "success", "message": f"App '{body.id}' deleted."}
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            db.rollback()
            logger.exception("Error deleting app configuration: %s", body.id)
            raise HTTPException(status_code=500, detail=f"Error deleting app configuration: {str(e)}")

    @router.post("/api/apps/compile")
    def handle_compile(request: Request) -> dict[str, Any]:
        """API POST endpoint to force cache invalidation and compilation."""
        try:
            invalidate_export_cache()
            base_url = get_base_url(request, ext.config.DEFAULT_PORT)
            compiled_data = ext.compiler.compile_master(base_url)
            return {
                "status": "success",
                "message": "Cache invalidated and configuration compiled successfully.",
                "count": len(compiled_data.get("apps", [])),
            }
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            logger.exception("Error during configuration compile")
            raise HTTPException(status_code=500, detail=f"Error during configuration compile: {str(e)}")

    @router.post("/api/settings/save")
    def handle_save_settings(data: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
        """API POST endpoint to save global settings in the database."""
        try:
            for k, v in data.items():
                if k == "categories":
                    input_cats = v if isinstance(v, dict) else {}
                    for cat_name, cat_color in input_cats.items():
                        cat = db.query(Category).filter_by(name=cat_name).first()
                        if cat:
                            cat.color = cat_color
                        else:
                            db.add(Category(name=cat_name, color=cat_color))
                    for db_cat in db.query(Category).all():
                        if db_cat.name not in input_cats:
                            db.delete(db_cat)
                else:
                    setting = db.query(Setting).filter_by(key=k).first()
                    if setting:
                        setting.value = v
                    else:
                        db.add(Setting(key=k, value=v))

            db.commit()
            invalidate_export_cache()
            return {"status": "success", "message": "Global settings saved."}
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            db.rollback()
            logger.exception("Error saving global settings")
            raise HTTPException(status_code=500, detail=f"Error saving global settings: {str(e)}")

    @router.post("/api/apps/local-apks")
    def handle_local_apk_upload(
        file: UploadFile = File(...),
        app_id: str = Form(...),
        version: str = Form(...),
        architecture: Optional[str] = Form(None),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """POST /api/apps/local-apks - Atomic file upload and metadata registration."""
        try:
            file_content = file.file.read()
        except IOError as e:
            logger.exception("Failed to read uploaded file")
            raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {str(e)}")

        if not file_content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        app = db.query(App).filter_by(id=app_id).first()
        if not app:
            raise HTTPException(status_code=404, detail=f"Application '{app_id}' is not registered in the database.")

        arch: Optional[str] = architecture
        if not arch or arch in ("none", "auto"):
            arch = None

        storage_ext = ext.storage_ext
        if not storage_ext:
            raise HTTPException(status_code=500, detail="Storage provider is not initialized.")

        try:
            file_hash = storage_ext.save_file(file_content)
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            logger.exception("Failed to save file to storage")
            raise HTTPException(status_code=500, detail=f"Failed to save file to storage: {str(e)}")

        try:
            apk = db.query(LocalAppAPK).filter_by(
                app_id=app_id,
                version=version,
                architecture=arch,
            ).first()

            if apk:
                old_hash = apk.file_hash
                apk.file_hash = file_hash
                db.commit()
                if old_hash != file_hash:
                    try:
                        storage_ext.delete_file(old_hash)
                    except Exception:  # noqa: BLE001 - best-effort cleanup
                        pass
            else:
                apk = LocalAppAPK(
                    app_id=app_id,
                    version=version,
                    architecture=arch,
                    file_hash=file_hash,
                )
                db.add(apk)
                db.commit()

            invalidate_export_cache()
            return {
                "status": "success",
                "message": "APK file and metadata registered successfully.",
                "id": apk.id,
                "file_hash": file_hash,
            }
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            db.rollback()
            try:
                storage_ext.delete_file(file_hash)
            except Exception as ex:  # noqa: BLE001 - best-effort rollback
                logger.error("Error rolling back physical file write: %s", ex)
            logger.exception("Database error during registration")
            raise HTTPException(status_code=500, detail=f"Database error during registration: {str(e)}")

    @router.delete("/api/apps/local-apks/{apk_id}")
    def handle_delete_mapping(apk_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
        """DELETE /api/apps/local-apks/{apk_id} - Removes APK metadata link from DB and triggers storage cleanup."""
        try:
            apk = db.query(LocalAppAPK).filter_by(id=apk_id).first()
            if not apk:
                raise HTTPException(status_code=404, detail=f"APK metadata ID '{apk_id}' not found")

            file_hash = apk.file_hash
            db.delete(apk)
            db.commit()
            invalidate_export_cache()

            storage_ext = ext.storage_ext
            if storage_ext:
                storage_ext.delete_file(file_hash)

            return {"status": "success", "message": "Local APK metadata mapping deleted successfully."}
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            db.rollback()
            logger.exception("Error deleting APK metadata: %s", apk_id)
            raise HTTPException(status_code=500, detail=f"Error deleting APK metadata: {str(e)}")

    @router.post("/api/apps/import")
    def handle_import_settings(data: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
        """POST /api/apps/import - Imports an Obtainium export JSON into the database."""
        if not isinstance(data, dict) or ("apps" not in data and "settings" not in data):
            raise HTTPException(status_code=400, detail="JSON must contain 'apps' or 'settings' key")

        try:
            imported_count = 0
            for app in data.get("apps", []):
                app_id = ext.cli_manager.import_app_config(app, db)
                if app_id:
                    imported_count += 1

            settings_data = data.get("settings")
            if settings_data:
                for k, v in settings_data.items():
                    if k == "categories":
                        parsed_cats = v
                        if isinstance(v, str):
                            try:
                                parsed_cats = json.loads(v)
                            except json.JSONDecodeError:
                                logger.warning("Failed to parse categories string as JSON: %s", v)
                                parsed_cats = {}
                        for cat_name, cat_color in parsed_cats.items():
                            cat = db.query(Category).filter_by(name=cat_name).first()
                            if cat:
                                cat.color = cat_color
                            else:
                                db.add(Category(name=cat_name, color=cat_color))
                    else:
                        setting = db.query(Setting).filter_by(key=k).first()
                        if setting:
                            setting.value = v
                        else:
                            db.add(Setting(key=k, value=v))

            db.commit()
            invalidate_export_cache()
            return {
                "status": "success",
                "message": f"Successfully imported {imported_count} apps and settings.",
                "count": imported_count,
            }
        except Exception as e:  # noqa: BLE001 - HTTP boundary
            db.rollback()
            logger.exception("Error importing configurations")
            raise HTTPException(status_code=500, detail=f"Error importing configurations: {str(e)}")

    return router
