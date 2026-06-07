from datetime import datetime
import asyncio
from fastapi import APIRouter
from backend.extensions.base import BaseExtension
from .manager_cli import ControlPlaneManagerCLI
from .api import router as api_router
from .ws import router as ws_router
from .core import set_main_loop


class ControlPlaneExtension(BaseExtension):
    """
    Control Plane extension for the portal.
    Manages devices, ACLs, bootstrap tokens, and operation dispatch.
    """

    def __init__(self, core_config, ext_config=None):
        super().__init__(core_config)
        self.ext_config = ext_config or {}
        self.tags = ["control-plane"]
        self.cli_manager = None
        merged = APIRouter()
        merged.include_router(api_router)
        merged.include_router(ws_router)
        self.router = merged

    def setup(self):
        self.cli_manager = ControlPlaneManagerCLI(self.config)

    def install_event_loop_capture(self, app):
        """Registers a FastAPI startup hook to capture the main asyncio loop."""
        @app.on_event("startup")
        async def _capture_loop():
            set_main_loop(asyncio.get_event_loop())

    def register_cli_commands(self, subparsers):
        if not self.cli_manager:
            self.setup()
        self.cli_manager.register_commands(subparsers)

    def get_routes(self):
        return {}

    def get_post_routes(self):
        return {}

    def backup_data(self, session) -> dict:
        from .models import Device, DeviceACL, DeviceBootstrapToken, OperationSpec, CommandRequest

        devices = [
            {
                "id": d.id,
                "display_name": d.display_name,
                "bearer_token": d.bearer_token,
                "ws_state": d.ws_state,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                "extra": d.extra,
                "registered_at": d.registered_at.isoformat() if d.registered_at else None,
                "is_first_webui_device": d.is_first_webui_device,
            }
            for d in session.query(Device).all()
        ]

        acls = [
            {
                "id": a.id,
                "source_device": a.source_device,
                "target_device": a.target_device,
                "operation": a.operation,
                "extra": a.extra,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in session.query(DeviceACL).all()
        ]

        bootstrap_tokens = [
            {
                "id": t.id,
                "device_id": t.device_id,
                "display_name": t.display_name,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "consumed_at": t.consumed_at.isoformat() if t.consumed_at else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in session.query(DeviceBootstrapToken).all()
        ]

        operations = [
            {
                "id": o.id,
                "provider": o.provider,
                "group": o.group,
                "name": o.name,
                "description": o.description,
                "params_schema": o.params_schema,
                "result_schema": o.result_schema,
                "ui_hint": o.ui_hint,
                "registered_at": o.registered_at.isoformat() if o.registered_at else None,
                "last_seen": o.last_seen.isoformat() if o.last_seen else None,
            }
            for o in session.query(OperationSpec).all()
        ]

        commands = [
            {
                "id": c.id,
                "target_device_id": c.target_device_id,
                "source_device_id": c.source_device_id,
                "operation": c.operation,
                "params": c.params,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "claimed_at": c.claimed_at.isoformat() if c.claimed_at else None,
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
                "result": c.result,
                "error": c.error,
                "claim_token": c.claim_token,
                "timeout_seconds": c.timeout_seconds,
            }
            for c in session.query(CommandRequest).all()
        ]

        return {
            "ctrl_devices": devices,
            "ctrl_device_acls": acls,
            "ctrl_bootstrap_tokens": bootstrap_tokens,
            "ctrl_operation_specs": operations,
            "ctrl_command_requests": commands,
        }

    def restore_data(self, session, data: dict, strategy: str):
        from .models import Device, DeviceACL, DeviceBootstrapToken, OperationSpec, CommandRequest

        if strategy == "overwrite":
            for model in (CommandRequest, OperationSpec, DeviceBootstrapToken, DeviceACL, Device):
                session.query(model).delete()
            session.flush()

        def _parse_dt(value):
            if not value:
                return None
            return datetime.fromisoformat(value)

        for d in data.get("ctrl_devices", []):
            existing = session.query(Device).filter_by(id=d["id"]).first()
            if existing and strategy == "merge":
                existing.display_name = d.get("display_name", existing.display_name)
                existing.bearer_token = d.get("bearer_token", existing.bearer_token)
                existing.ws_state = d.get("ws_state", existing.ws_state)
                existing.last_seen = _parse_dt(d.get("last_seen"))
                existing.extra = d.get("extra", existing.extra)
                existing.is_first_webui_device = d.get("is_first_webui_device", existing.is_first_webui_device)
            else:
                session.add(Device(
                    id=d["id"],
                    display_name=d["display_name"],
                    bearer_token=d["bearer_token"],
                    ws_state=d.get("ws_state", "never_connected"),
                    last_seen=_parse_dt(d.get("last_seen")),
                    extra=d.get("extra"),
                    registered_at=_parse_dt(d.get("registered_at")) or datetime.utcnow(),
                    is_first_webui_device=d.get("is_first_webui_device", False),
                ))
        session.flush()

        for a in data.get("ctrl_device_acls", []):
            existing = session.query(DeviceACL).filter_by(id=a["id"]).first()
            if existing:
                continue
            session.add(DeviceACL(
                id=a["id"],
                source_device=a["source_device"],
                target_device=a["target_device"],
                operation=a["operation"],
                extra=a.get("extra"),
                created_at=_parse_dt(a.get("created_at")) or datetime.utcnow(),
            ))
        session.flush()

        for t in data.get("ctrl_bootstrap_tokens", []):
            existing = session.query(DeviceBootstrapToken).filter_by(id=t["id"]).first()
            if existing:
                continue
            session.add(DeviceBootstrapToken(
                id=t["id"],
                device_id=t["device_id"],
                display_name=t["display_name"],
                expires_at=_parse_dt(t["expires_at"]),
                consumed_at=_parse_dt(t.get("consumed_at")),
                created_at=_parse_dt(t.get("created_at")) or datetime.utcnow(),
            ))
        session.flush()

        for o in data.get("ctrl_operation_specs", []):
            existing = session.query(OperationSpec).filter_by(
                provider=o["provider"], id=o["id"]
            ).first()
            if existing:
                continue
            session.add(OperationSpec(
                id=o["id"],
                provider=o["provider"],
                group=o["group"],
                name=o["name"],
                description=o.get("description"),
                params_schema=o.get("params_schema") or {},
                result_schema=o.get("result_schema"),
                ui_hint=o.get("ui_hint"),
                registered_at=_parse_dt(o.get("registered_at")) or datetime.utcnow(),
                last_seen=_parse_dt(o.get("last_seen")),
            ))
        session.flush()

        for c in data.get("ctrl_command_requests", []):
            existing = session.query(CommandRequest).filter_by(id=c["id"]).first()
            if existing:
                continue
            session.add(CommandRequest(
                id=c["id"],
                target_device_id=c["target_device_id"],
                source_device_id=c["source_device_id"],
                operation=c["operation"],
                params=c.get("params") or {},
                status=c.get("status", "pending"),
                created_at=_parse_dt(c.get("created_at")) or datetime.utcnow(),
                claimed_at=_parse_dt(c.get("claimed_at")),
                completed_at=_parse_dt(c.get("completed_at")),
                result=c.get("result"),
                error=c.get("error"),
                claim_token=c.get("claim_token"),
                timeout_seconds=c.get("timeout_seconds", 60),
            ))
        session.flush()

    def get_startup_info(self, local_ip: str) -> list:
        return [
            f"Control Plane:  http://{local_ip}:{self.config.DEFAULT_PORT}/api/control/  (Phase 2: REST API)"
        ]
