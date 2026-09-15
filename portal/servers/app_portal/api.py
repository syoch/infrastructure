import json
import re
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.server_base import require_admin_device
from .models import WebApp, Feedback, Bridge
from .opencode_ops import ROLE_KEYS, TRAITS_OPERATION_ID, server_key_for


router = APIRouter(prefix="/api/app-portal", tags=["app-portal"])

# Runtime configuration injected by the extension's setup()
_settings = {"bridge_device_id": "opencode-bridge"}

# In-process cache of per-device opencode-bridge metadata discovered through the
# `traits.opencode-bridge` operation: {"roles": {role: op_id}, "webui_base_url", "server_key"}
_meta_cache: dict[str, dict] = {}


def configure(bridge_device_id: str) -> None:
    _settings["bridge_device_id"] = bridge_device_id


def _device_required(
    authorization: str = Header(default=""),
    token: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Requires any registered control-plane device (Bearer token)."""
    from servers.control_plane.core import get_current_device

    return get_current_device(authorization=authorization, token=token, db=db)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or uuid.uuid4().hex[:12]


def _parse_op_result(result) -> dict:
    """Normalizes a control-plane command result.

    The generic device agent reports `{"stdout", "stderr", "exit_code"}` and the
    opencode helper CLI prints a JSON object on stdout; older shapes may already
    carry the payload at the top level.
    """
    if not isinstance(result, dict):
        return {}
    if "stdout" in result:
        raw = (result.get("stdout") or "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return result


def _bridge(db: Session, device_id: str) -> Optional[Bridge]:
    return db.query(Bridge).filter(Bridge.device_id == device_id).first()


def webui_url_for(db: Session, app: WebApp) -> Optional[str]:
    br = _bridge(db, app.bridge_device_id)
    if br and br.webui_base_url and br.server_key:
        return f"{br.webui_base_url.rstrip('/')}/server/{br.server_key}/session/{app.opencode_session_id}"
    # Fall back to the most recent delivered feedback's deep link.
    last = (
        db.query(Feedback)
        .filter(Feedback.app_id == app.id, Feedback.webui_url.isnot(None))
        .order_by(Feedback.created_at.desc())
        .first()
    )
    return last.webui_url if last else None


def _device_online(db: Session, device_id: str) -> bool:
    from servers.control_plane.models import Device

    d = db.query(Device).filter_by(id=device_id).first()
    return bool(d and d.ws_state == "online")


def _opencode_meta(db: Session, source_device, device_id: str, timeout: float = 8.0) -> dict:
    """Discovers the target device's `opencode-bridge` trait.

    Returns {"roles": {role: op_id}, "webui_base_url", "server_key"} (possibly
    empty). Result is cached in-process and the WebUI info is persisted.
    """
    cached = _meta_cache.get(device_id)
    if cached:
        return cached
    if not _device_online(db, device_id):
        return {}
    try:
        from servers.control_plane.core import enqueue_command
        from servers.control_plane.models import CommandRequest

        cmd = enqueue_command(
            db,
            source_device=source_device,
            target_device_id=device_id,
            operation=TRAITS_OPERATION_ID,
            params={},
            timeout_seconds=max(1, int(timeout)),
        )
        cur = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            db.expire_all()
            cur = db.query(CommandRequest).filter_by(id=cmd.id).first()
            if cur and cur.status in ("succeeded", "failed", "timeout", "cancelled"):
                break
            time.sleep(0.2)
        payload = _parse_op_result(cur.result if cur else None)
        if not payload:
            return {}
        webui_base_url = payload.get("webui_base_url")
        server_key = payload.get("server_key") or (
            server_key_for(webui_base_url) if webui_base_url else None
        )
        meta = {
            "roles": payload.get("operations") or {},
            "webui_base_url": webui_base_url,
            "server_key": server_key,
        }
        _meta_cache[device_id] = meta
        if webui_base_url and server_key:
            br = _bridge(db, device_id)
            if not br:
                br = Bridge(device_id=device_id)
                db.add(br)
            br.webui_base_url = webui_base_url
            br.server_key = server_key
            br.last_seen = datetime.utcnow()
            db.commit()
        return meta
    except Exception:  # noqa: BLE001 - discovery is best-effort
        return {}


def _reconcile(db: Session, fb: Feedback) -> Feedback:
    """Lazily reflect the control-plane command status onto a feedback row."""
    if fb.status != "pending" or not fb.command_id:
        return fb
    from servers.control_plane.models import CommandRequest

    cmd = db.query(CommandRequest).filter_by(id=fb.command_id).first()
    if cmd is None:
        return fb
    if cmd.status == "succeeded":
        fb.status = "delivered"
        fb.delivered_at = cmd.completed_at or datetime.utcnow()
        payload = _parse_op_result(cmd.result)
        fb.webui_url = payload.get("webui_url") or fb.webui_url
        fb.target_session_id = payload.get("session_id") or fb.target_session_id
    elif cmd.status in ("failed", "timeout", "cancelled"):
        fb.status = "failed"
        fb.error = cmd.error or f"command {cmd.status}"
    return fb


def _feedback_to_dict(fb: Feedback) -> dict:
    return {
        "id": fb.id,
        "app_id": fb.app_id,
        "author": fb.author,
        "body": fb.body,
        "kind": fb.kind,
        "status": fb.status,
        "command_id": fb.command_id,
        "target_session_id": fb.target_session_id,
        "webui_url": fb.webui_url,
        "delivered_at": _iso(fb.delivered_at),
        "error": fb.error,
        "created_at": _iso(fb.created_at),
    }


def _app_to_dict(db: Session, app: WebApp, include_feedback: bool = False) -> dict:
    data = {
        "id": app.id,
        "slug": app.slug,
        "name": app.name,
        "description": app.description,
        "url": app.url,
        "project_directory": app.project_directory,
        "opencode_session_id": app.opencode_session_id,
        "bridge_device_id": app.bridge_device_id,
        "source": app.source,
        "tags": app.tags or [],
        "status": app.status,
        "webui_url": webui_url_for(db, app),
        "created_at": _iso(app.created_at),
        "updated_at": _iso(app.updated_at),
        "created_by": app.created_by,
    }
    if include_feedback:
        fbs = (
            db.query(Feedback)
            .filter(Feedback.app_id == app.id)
            .order_by(Feedback.created_at.desc())
            .all()
        )
        data["feedback"] = [_feedback_to_dict(_reconcile(db, fb)) for fb in fbs]
        db.commit()
    return data


def _get_app_or_404(db: Session, slug: str) -> WebApp:
    app = db.query(WebApp).filter(WebApp.slug == slug).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"app {slug!r} not found")
    return app


def _prompt_for(app: WebApp, fb: Feedback) -> str:
    author = fb.author or "unknown"
    return (
        f"[App Portal Feedback]\n"
        f"app: {app.name} ({app.slug})\n"
        f"kind: {fb.kind}\n"
        f"from: {author}\n\n"
        f"{fb.body}"
    )


# --- Request bodies ---

class AppCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: Optional[str] = None
    url: Optional[str] = None
    project_directory: str = Field(min_length=1)
    opencode_session_id: str = Field(min_length=1)
    slug: Optional[str] = None
    bridge_device_id: Optional[str] = None
    source: str = "manual"
    tags: list[str] = Field(default_factory=list)
    created_by: Optional[str] = None


class AppUpdateBody(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    project_directory: Optional[str] = None
    opencode_session_id: Optional[str] = None
    bridge_device_id: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


class FeedbackBody(BaseModel):
    body: str = Field(min_length=1)
    kind: str = "feedback"
    author: Optional[str] = None


class BridgeAnnounceBody(BaseModel):
    webui_base_url: str = Field(min_length=1)
    server_key: Optional[str] = None
    hostname: Optional[str] = None


# --- Routes ---

@router.get("/apps")
def list_apps(
    device=Depends(_device_required),
    db: Session = Depends(get_db),
):
    apps = db.query(WebApp).order_by(WebApp.created_at.desc()).all()
    return {"apps": [_app_to_dict(db, a) for a in apps]}


@router.post("/apps")
def create_app(
    body: AppCreateBody,
    device=Depends(_device_required),
    db: Session = Depends(get_db),
):
    slug = body.slug or _slugify(body.name)
    if db.query(WebApp).filter(WebApp.slug == slug).first():
        raise HTTPException(status_code=409, detail=f"app slug {slug!r} already exists")
    bridge_device_id = body.bridge_device_id or _settings["bridge_device_id"]
    app = WebApp(
        slug=slug,
        name=body.name,
        description=body.description,
        url=body.url,
        project_directory=body.project_directory,
        opencode_session_id=body.opencode_session_id,
        bridge_device_id=bridge_device_id,
        source=body.source,
        tags=body.tags,
        created_by=body.created_by or getattr(device, "id", None),
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return _app_to_dict(db, app)


@router.get("/apps/{slug}")
def get_app(
    slug: str,
    device=Depends(_device_required),
    db: Session = Depends(get_db),
):
    app = _get_app_or_404(db, slug)
    # Warm the opencode-bridge metadata cache so the session deep link can be
    # shown even before the first feedback is delivered.
    if _bridge(db, app.bridge_device_id) is None:
        _opencode_meta(db, device, app.bridge_device_id, timeout=4.0)
    return _app_to_dict(db, app, include_feedback=True)


@router.patch("/apps/{slug}")
def update_app(
    slug: str,
    body: AppUpdateBody,
    device=Depends(require_admin_device),
    db: Session = Depends(get_db),
):
    app = _get_app_or_404(db, slug)
    for field in (
        "name", "description", "url", "project_directory",
        "opencode_session_id", "bridge_device_id", "tags", "status",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(app, field, value)
    db.commit()
    db.refresh(app)
    return _app_to_dict(db, app)


@router.delete("/apps/{slug}")
def delete_app(
    slug: str,
    device=Depends(require_admin_device),
    db: Session = Depends(get_db),
):
    app = _get_app_or_404(db, slug)
    db.delete(app)
    db.commit()
    return {"status": "success", "deleted": slug}


@router.post("/apps/{slug}/feedback")
def submit_feedback(
    slug: str,
    body: FeedbackBody,
    device=Depends(require_admin_device),
    db: Session = Depends(get_db),
):
    app = _get_app_or_404(db, slug)
    if not app.opencode_session_id:
        raise HTTPException(status_code=400, detail="app has no pinned OpenCode session")

    fb = Feedback(
        app_id=app.id,
        author=body.author or getattr(device, "id", None),
        body=body.body,
        kind=body.kind,
        status="pending",
        target_session_id=app.opencode_session_id,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    try:
        from servers.control_plane.core import enqueue_command
        from servers.control_plane.models import Device as ControlDevice

        bridge_dev = db.query(ControlDevice).filter_by(id=app.bridge_device_id).first()
        if bridge_dev is None:
            fb.status = "failed"
            fb.error = f"bridge device {app.bridge_device_id!r} is not registered"
            db.commit()
            db.refresh(fb)
            return _feedback_to_dict(fb)

        meta = _opencode_meta(db, device, app.bridge_device_id)
        feedback_op = (meta.get("roles") or {}).get("feedback", ROLE_KEYS["feedback"])

        cmd = enqueue_command(
            db,
            source_device=device,
            target_device_id=app.bridge_device_id,
            operation=feedback_op,
            params={
                "session_id": app.opencode_session_id,
                "prompt": _prompt_for(app, fb),
                "app_slug": app.slug,
            },
            timeout_seconds=120,
        )
        fb.command_id = cmd.id
        db.commit()
        db.refresh(fb)
    except Exception as e:  # noqa: BLE001 - surface any delivery failure on the feedback row
        fb.status = "failed"
        fb.error = f"failed to enqueue delivery command: {e}"
        db.commit()

    return _feedback_to_dict(fb)


@router.get("/feedback")
def list_feedback(
    device=Depends(require_admin_device),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
):
    rows = db.query(Feedback).order_by(Feedback.created_at.desc()).limit(limit).all()
    result = [_feedback_to_dict(_reconcile(db, fb)) for fb in rows]
    db.commit()
    return {"feedback": result}


@router.post("/feedback/{feedback_id}/refresh")
def refresh_feedback(
    feedback_id: str,
    device=Depends(require_admin_device),
    db: Session = Depends(get_db),
):
    fb = db.query(Feedback).filter_by(id=feedback_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail=f"feedback {feedback_id!r} not found")
    _reconcile(db, fb)
    db.commit()
    db.refresh(fb)
    return _feedback_to_dict(fb)


@router.post("/bridges/announce")
def announce_bridge(
    body: BridgeAnnounceBody,
    device=Depends(_device_required),
    db: Session = Depends(get_db),
):
    br = _bridge(db, device.id)
    if not br:
        br = Bridge(device_id=device.id)
        db.add(br)
    br.hostname = body.hostname or br.hostname
    br.webui_base_url = body.webui_base_url
    br.server_key = body.server_key or server_key_for(body.webui_base_url)
    br.last_seen = datetime.utcnow()
    db.commit()
    db.refresh(br)
    return {
        "status": "ok",
        "device_id": br.device_id,
        "webui_base_url": br.webui_base_url,
        "server_key": br.server_key,
    }


@router.get("/bridges")
def list_bridges(
    device=Depends(require_admin_device),
    db: Session = Depends(get_db),
):
    bridges = db.query(Bridge).order_by(Bridge.registered_at).all()
    return {
        "bridges": [
            {
                "device_id": b.device_id,
                "hostname": b.hostname,
                "webui_base_url": b.webui_base_url,
                "server_key": b.server_key,
                "last_seen": _iso(b.last_seen),
                "registered_at": _iso(b.registered_at),
            }
            for b in bridges
        ]
    }
