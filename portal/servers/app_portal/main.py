from datetime import datetime

from fastapi import APIRouter

from backend.extensions.base import BaseExtension
from .api import router as api_router, configure
from .manager_cli import AppPortalManagerCLI


class AppPortalExtension(BaseExtension):
    """
    App Portal extension: registry of OpenCode-created (and manually registered)
    web apps, plus feedback delivery to their pinned OpenCode sessions via the
    control-plane command channel.
    """

    def __init__(self, core_config, ext_config=None):
        super().__init__(core_config)
        self.ext_config = ext_config or {}
        self.tags = ["app-portal"]
        self.bridge_device_id = self.ext_config.get("bridge_device_id", "opencode-bridge")
        self.cli_manager = None
        self.router = api_router

    def setup(self):
        configure(self.bridge_device_id)
        self.cli_manager = AppPortalManagerCLI(self.config)

    def register_cli_commands(self, subparsers):
        if not self.cli_manager:
            self.setup()
        self.cli_manager.register_commands(subparsers)

    def get_startup_info(self, local_ip: str) -> list:
        return [
            f"App Portal:     http://{local_ip}:{self.config.DEFAULT_PORT}/#/apps"
        ]

    def backup_data(self, session) -> dict:
        from .models import WebApp, Feedback, Bridge

        apps = [
            {
                "id": a.id,
                "slug": a.slug,
                "name": a.name,
                "description": a.description,
                "url": a.url,
                "project_directory": a.project_directory,
                "opencode_session_id": a.opencode_session_id,
                "bridge_device_id": a.bridge_device_id,
                "source": a.source,
                "tags": a.tags or [],
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                "created_by": a.created_by,
            }
            for a in session.query(WebApp).all()
        ]

        feedback = [
            {
                "id": f.id,
                "app_id": f.app_id,
                "author": f.author,
                "body": f.body,
                "kind": f.kind,
                "status": f.status,
                "command_id": f.command_id,
                "target_session_id": f.target_session_id,
                "webui_url": f.webui_url,
                "delivered_at": f.delivered_at.isoformat() if f.delivered_at else None,
                "error": f.error,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in session.query(Feedback).all()
        ]

        bridges = [
            {
                "device_id": b.device_id,
                "hostname": b.hostname,
                "webui_base_url": b.webui_base_url,
                "server_key": b.server_key,
                "last_seen": b.last_seen.isoformat() if b.last_seen else None,
                "registered_at": b.registered_at.isoformat() if b.registered_at else None,
            }
            for b in session.query(Bridge).all()
        ]

        return {
            "app_portal_web_apps": apps,
            "app_portal_feedback": feedback,
            "app_portal_bridges": bridges,
        }

    def restore_data(self, session, data: dict, strategy: str):
        from .models import WebApp, Feedback, Bridge

        def _parse_dt(value):
            if not value:
                return None
            return datetime.fromisoformat(value)

        if strategy == "overwrite":
            for model in (Feedback, WebApp, Bridge):
                session.query(model).delete()
            session.flush()

        for a in data.get("app_portal_web_apps", []):
            existing = session.query(WebApp).filter_by(id=a["id"]).first()
            if existing and strategy == "merge":
                existing.slug = a.get("slug", existing.slug)
                existing.name = a.get("name", existing.name)
                existing.description = a.get("description", existing.description)
                existing.url = a.get("url", existing.url)
                existing.project_directory = a.get("project_directory", existing.project_directory)
                existing.opencode_session_id = a.get("opencode_session_id", existing.opencode_session_id)
                existing.bridge_device_id = a.get("bridge_device_id", existing.bridge_device_id)
                existing.source = a.get("source", existing.source)
                existing.tags = a.get("tags", existing.tags)
                existing.status = a.get("status", existing.status)
            else:
                session.add(WebApp(
                    id=a["id"],
                    slug=a["slug"],
                    name=a["name"],
                    description=a.get("description"),
                    url=a.get("url"),
                    project_directory=a["project_directory"],
                    opencode_session_id=a["opencode_session_id"],
                    bridge_device_id=a["bridge_device_id"],
                    source=a.get("source", "manual"),
                    tags=a.get("tags") or [],
                    status=a.get("status", "active"),
                    created_at=_parse_dt(a.get("created_at")) or datetime.utcnow(),
                    updated_at=_parse_dt(a.get("updated_at")) or datetime.utcnow(),
                    created_by=a.get("created_by"),
                ))
        session.flush()

        for f in data.get("app_portal_feedback", []):
            if session.query(Feedback).filter_by(id=f["id"]).first():
                continue
            session.add(Feedback(
                id=f["id"],
                app_id=f["app_id"],
                author=f.get("author"),
                body=f["body"],
                kind=f.get("kind", "feedback"),
                status=f.get("status", "pending"),
                command_id=f.get("command_id"),
                target_session_id=f.get("target_session_id"),
                webui_url=f.get("webui_url"),
                delivered_at=_parse_dt(f.get("delivered_at")),
                error=f.get("error"),
                created_at=_parse_dt(f.get("created_at")) or datetime.utcnow(),
            ))
        session.flush()

        for b in data.get("app_portal_bridges", []):
            existing = session.query(Bridge).filter_by(device_id=b["device_id"]).first()
            if existing:
                continue
            session.add(Bridge(
                device_id=b["device_id"],
                hostname=b.get("hostname"),
                webui_base_url=b.get("webui_base_url"),
                server_key=b.get("server_key"),
                last_seen=_parse_dt(b.get("last_seen")),
                registered_at=_parse_dt(b.get("registered_at")) or datetime.utcnow(),
            ))
        session.flush()
