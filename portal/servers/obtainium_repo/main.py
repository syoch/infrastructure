"""Obtainium repository extension lifecycle.

HTTP routes live in :mod:`servers.obtainium_repo.api`; this module keeps the
extension class plus its backup/restore and CLI hooks.
"""
import logging

from backend.extensions.base import BaseExtension
from .models import App, Category, LocalAppAPK, Setting
from .compiler import ObtainiumConfigCompiler
from .manager_cli import ObtainiumRepoManagerCLI
from .api import build_router, invalidate_export_cache

logger = logging.getLogger(__name__)


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
        self.router = build_router(self)

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
        categories = [
            {"name": cat.name, "color": cat.color}
            for cat in session.query(Category).all()
        ]
        apps = [
            {
                "id": app.id,
                "name": app.name,
                "url": app.url,
                "override_source": app.override_source,
                "preferred_apk_index": app.preferred_apk_index,
                "pinned": app.pinned,
                "allow_id_change": app.allow_id_change,
                "additional_settings": app.additional_settings,
                "categories": [c.name for c in app.categories],
            }
            for app in session.query(App).all()
        ]
        settings = [
            {"key": setting.key, "value": setting.value}
            for setting in session.query(Setting).all()
        ]
        local_apks = [
            {
                "app_id": apk.app_id,
                "file_hash": apk.file_hash,
                "version": apk.version,
                "architecture": apk.architecture,
            }
            for apk in session.query(LocalAppAPK).all()
        ]

        return {
            "categories": categories,
            "apps": apps,
            "settings": settings,
            "local_app_apks": local_apks,
        }

    def restore_data(self, session, data: dict, strategy: str):
        """Deserializes App, Category, Setting, and LocalAppAPK records."""
        logger.info("Restoring Category records...")
        for cat_data in data.get("categories", []):
            cat = session.query(Category).filter_by(name=cat_data["name"]).first()
            if not cat:
                cat = Category(name=cat_data["name"], color=cat_data["color"])
                session.add(cat)
            else:
                cat.color = cat_data["color"]
        session.flush()

        logger.info("Restoring App records...")
        for app_data in data.get("apps", []):
            categories_list = app_data.pop("categories", [])

            # Rewrite Self-Hosted app source URL containing scrape-index.html to avoid hardcoded IP/port
            if app_data.get("override_source") == "HTML" and "scrape-index.html" in app_data.get("url", ""):
                logger.info(
                    "Sanitizing Self-Hosted APK source URL for app %s: %s -> /scrape-index.html",
                    app_data.get("id"),
                    app_data["url"],
                )
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

            app.categories = []
            for cat_name in categories_list:
                cat = session.query(Category).filter_by(name=cat_name).first()
                if cat:
                    app.categories.append(cat)
        session.flush()

        logger.info("Restoring LocalAppAPK records...")
        for apk_data in data.get("local_app_apks", []):
            existing = session.query(LocalAppAPK).filter_by(
                app_id=apk_data["app_id"],
                file_hash=apk_data["file_hash"],
                version=apk_data["version"],
                architecture=apk_data.get("architecture"),
            ).first()
            if not existing:
                parent_app = session.query(App).filter_by(id=apk_data["app_id"]).first()
                if parent_app:
                    session.add(LocalAppAPK(
                        app_id=apk_data["app_id"],
                        file_hash=apk_data["file_hash"],
                        version=apk_data["version"],
                        architecture=apk_data.get("architecture"),
                    ))
        session.flush()

        logger.info("Restoring Setting records...")
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
