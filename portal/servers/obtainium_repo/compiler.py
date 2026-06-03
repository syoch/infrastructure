import os
import json
import time
from urllib.parse import urlparse
from sqlalchemy.orm import selectinload
from backend.core.database import get_session
from .models import App, Category, Setting

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
        db_apps = session.query(App).options(
            selectinload(App.categories),
            selectinload(App.apks)
        ).order_by(App.id).all()

        compiled_apps = []
        for app in db_apps:
            try:
                compiled_apps.append(self._build_app(app, base_url))
            except Exception as e:
                print(f"Error compiling app config {app.id}: {e}")

        master_export = {"apps": compiled_apps}
        settings = self._build_settings(session)
        if settings:
            master_export["settings"] = settings
        return master_export

    def _build_app(self, app, base_url):
        is_self_hosted = bool(app.apks)
        if is_self_hosted:
            url = f"{base_url}/scrape-index.html"
            override_source = self._OVERRIDE_SOURCE_SELF_HOSTED
        else:
            url = app.url
            override_source = app.override_source

        additional_settings = dict(app.additional_settings) if app.additional_settings else {}

        if is_self_hosted:
            latest_apk = sorted(app.apks, key=lambda x: x.id)[-1]
            escaped_name = app.name.replace(".", r"\.").replace(' ', '_')
            escaped_pkg = app.id.replace(".", r"\.")
            arch_str = f"_{latest_apk.architecture}" if latest_apk.architecture else ""
            v_prefix = "" if (
                latest_apk.version.lower().startswith('v')
                or latest_apk.version.lower().startswith('r')
            ) else "v"
            filename = f"{escaped_name}_{app.id}_{v_prefix}{latest_apk.version}{arch_str}.apk"
            apk_download_url = f"{base_url}/api/apps/download/{latest_apk.id}/{filename}"
            apk_urls = [[filename, apk_download_url]]
            other_asset_urls = []
            latest_version = latest_apk.version
            additional_settings.update({
                "apkFilterRegEx": f"^{escaped_name}_{escaped_pkg}_v.*\\.apk$",
                "versionExtractionRegEx": f"^{escaped_name}_{escaped_pkg}_v([^\\s_]+).*\\.apk$",
                "matchGroupToUse": 1,
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

    def _infer_author(self, url):
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

    def _build_settings(self, session):
        export_settings = {}
        try:
            db_settings = session.query(Setting).all()
            for s in db_settings:
                export_settings[s.key] = s.value
            db_cats = session.query(Category).all()
            if db_cats:
                categories_dict = {c.name: c.color for c in db_cats}
                export_settings["categories"] = json.dumps(categories_dict, ensure_ascii=False)
        except Exception as e:
            print(f"Error formulating export settings: {e}")
        return export_settings
