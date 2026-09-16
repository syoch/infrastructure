import re
import json
import logging
import time
from typing import Any, Optional
from urllib.parse import urlparse
from sqlalchemy.orm import Session, selectinload
from .models import App, Category, Setting
from .utils import export_apk_filename, select_latest_apk

logger = logging.getLogger(__name__)

class ObtainiumConfigCompiler:
    """
    Compiles database app configs and global settings into an Obtainium-compatible JSON structure.

    The output schema is a strict subset of what Obtainium's `App.toJson()` produces
    (see https://github.com/ImranR98/Obtainium/blob/main/lib/providers/source_provider.dart).
    All 18 required fields are emitted so the file can be used with Obtainium's
    "Obtainium Import" flow. A few portal-internal fields (prefixed with `_`) are
    also attached for the portal front-end.
    """

    _OVERRIDE_SOURCE_SELF_HOSTED = "HTML"

    def __init__(self, core_config: Any):
        self.config = core_config

    def compile_master(self, base_url: str, session: Optional[Session] = None) -> dict[str, Any]:
        """
        Loads all application configurations from the database,
        combining them with global configurations.
        """
        if session is not None:
            return self._compile_master_with_session(base_url, session)

        from backend.core.database import session_scope
        with session_scope() as session:
            return self._compile_master_with_session(base_url, session)

    def _compile_master_with_session(self, base_url: str, session: Session) -> dict[str, Any]:
        db_apps = session.query(App).options(
            selectinload(App.categories),
            selectinload(App.apks)
        ).order_by(App.id).all()

        compiled_apps: list[dict[str, Any]] = []
        for app in db_apps:
            try:
                compiled_apps.append(self._build_app(app, base_url))
            except Exception as e:
                logger.error("Error compiling app config %s: %s", app.id, e)

        master_export: dict[str, Any] = {"apps": compiled_apps}
        settings = self._build_settings(session)
        if settings:
            master_export["settings"] = settings
        return master_export

    def _build_app(self, app: App, base_url: str) -> dict[str, Any]:
        is_self_hosted = bool(app.apks)
        url: str
        override_source: Optional[str]
        if is_self_hosted:
            url = f"{base_url}/scrape-index.html"
            override_source = self._OVERRIDE_SOURCE_SELF_HOSTED
        else:
            url = app.url
            override_source = app.override_source

        additional_settings = dict(app.additional_settings) if app.additional_settings else {}

        if is_self_hosted:
            latest_apk = select_latest_apk(app.apks)
            filename = export_apk_filename(
                app.name, app.id, latest_apk.version, latest_apk.architecture
            )
            apk_download_url = f"{base_url}/api/apps/download/{latest_apk.id}/{filename}"
            apk_urls = [[filename, apk_download_url]]
            other_asset_urls: list[Any] = []
            latest_version = latest_apk.version
            # Obtainium applies both regexes to the *absolute download URL*
            # (see lib/services/apk_filter_service.dart filterApks() and
            # lib/app_sources/html.dart extractVersion()). Do not anchor to the
            # whole string or to the bare filename.
            pkg = re.escape(app.id)
            archs = sorted({a.architecture for a in app.apks if a.architecture})
            arch_group = (
                f"(?:_(?:{'|'.join(re.escape(a) for a in archs)}))?" if archs else ""
            )
            additional_settings.update({
                "apkFilterRegEx": f"_{pkg}_v[^/]+\\.apk$",
                "versionExtractionRegEx": f"_v([^/]+?){arch_group}\\.apk$",
                "matchGroupToUse": "1",
            })
        else:
            apk_urls = [["placeholder", "placeholder"]]
            other_asset_urls = []
            latest_version = None

        author = self._infer_author(url)
        now_micros = int(time.time() * 1_000_000)

        export = {
            "id": app.id,
            "url": url,
            "author": author,
            "name": app.name,
            "installedVersion": None,
            "latestVersion": latest_version,
            "apkUrls": json.dumps(apk_urls, ensure_ascii=False),
            "otherAssetUrls": json.dumps(other_asset_urls, ensure_ascii=False),
            "preferredApkIndex": app.preferred_apk_index,
            "additionalSettings": json.dumps(additional_settings, ensure_ascii=False),
            "lastUpdateCheck": now_micros,
            "pinned": bool(app.pinned),
            "categories": [c.name for c in app.categories],
            "releaseDate": None,
            "changeLog": None,
            "overrideSource": override_source,
            "allowIdChange": bool(app.allow_id_change),
            "pendingRepoRenameUrl": None,
        }

        # Portal-internal extras consumed by the front-end
        if is_self_hosted:
            export["_version"] = latest_apk.version
            export["_latest_apk_id"] = latest_apk.id
            export["_filename"] = filename

        return export

    def _infer_author(self, url: str) -> str:
        """Best-effort author inference from common source-host URL patterns.

        Obtainium requires `author` to be a non-null String. We extract a
        sensible value from known hosts and fall back to an empty string
        so the field is always present.
        """
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            parts = [p for p in parsed.path.split('/') if p]
            if host in ("github.com", "gitlab.com", "codeberg.org", "gitea.com", "git.sr.ht"):
                if parts:
                    return parts[0]
            if host == "sourceforge.net" and len(parts) >= 2 and parts[0] == "projects":
                return parts[1]
        except Exception:
            pass
        return ""

    def _build_settings(self, session: Session) -> dict[str, Any]:
        export_settings: dict[str, Any] = {}
        try:
            db_settings = session.query(Setting).all()
            for s in db_settings:
                export_settings[s.key] = s.value
            db_cats = session.query(Category).all()
            if db_cats:
                categories_dict = {c.name: c.color for c in db_cats}
                export_settings["categories"] = json.dumps(categories_dict, ensure_ascii=False)
        except Exception as e:
            logger.error("Error formulating export settings: %s", e)
        return export_settings
