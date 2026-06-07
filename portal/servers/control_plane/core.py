import asyncio
import json
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Optional, Any

from fastapi import Header, Query, HTTPException, Depends, status, Request, APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.core.database import get_db, get_session

from .models import Device, DeviceACL, DeviceBootstrapToken, OperationSpec, CommandRequest

log = logging.getLogger("control_plane.core")

# --- AUTHENTICATION ---

def _resolve_bearer_token(authorization: str, query_token: str = "") -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    if query_token:
        return query_token.strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing or invalid Authorization header (expected: Bearer <token>)",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_current_device(
    authorization: str = Header(default=""),
    token: str = Query(default=""),
    db: Session = Depends(get_db),
) -> Device:
    bearer = _resolve_bearer_token(authorization, token)
    if not bearer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="empty bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    device = db.query(Device).filter(Device.bearer_token == bearer).first()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device

def get_current_device_with_promotion(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> Device:
    has_admin = db.query(Device).filter(Device.is_first_webui_device == True).first()
    device.last_seen = datetime.utcnow()
    if has_admin is None:
        device.is_first_webui_device = True
    db.commit()
    db.refresh(device)
    return device

def require_admin(device: Device = Depends(get_current_device)) -> Device:
    if not device.is_first_webui_device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin privilege required (this device is not the first WebUI device)",
        )
    return device


# --- DISPATCHER & ACL ---

def _strip_type_prefix(value: str) -> str:
    if ":" in value:
        _, pattern = value.split(":", 1)
        return pattern
    return value

def can_issue(db: Session, source_id: str, target_id: str, operation: str) -> bool:
    acls = db.query(DeviceACL).all()
    for acl in acls:
        try:
            src_match = re.search(_strip_type_prefix(acl.source_device), source_id)
            tgt_match = re.search(_strip_type_prefix(acl.target_device), target_id)
            op_match = re.search(acl.operation, operation)
            if src_match and tgt_match and op_match:
                return True
        except re.error as e:
            log.warning(f"Invalid regex in ACL {acl.id}: {e}")
            continue
    return False

def resolve_provider(db: Session, operation_id: str, target_device_id: str) -> Optional[OperationSpec]:
    return (
        db.query(OperationSpec)
        .filter(OperationSpec.id == operation_id)
        .filter(OperationSpec.provider == f"device:{target_device_id}")
        .first()
    )

def provider_device_id(spec: OperationSpec) -> Optional[str]:
    if not spec or not spec.provider.startswith("device:"):
        return None
    return spec.provider.removeprefix("device:")

def filter_operations_for_device(db: Session, device: Device) -> list[OperationSpec]:
    all_specs = db.query(OperationSpec).all()
    if device.is_first_webui_device:
        return all_specs
    visible = []
    for spec in all_specs:
        target_id = provider_device_id(spec)
        if target_id is not None and can_issue(db, device.id, target_id, spec.id):
            visible.append(spec)
    return visible

def enqueue_command(
    db: Session,
    source_device: Device,
    target_device_id: str,
    operation: str,
    params: dict,
    timeout_seconds: int = 60,
) -> CommandRequest:
    cmd = CommandRequest(
        id=str(uuid.uuid4()),
        target_device_id=target_device_id,
        source_device_id=source_device.id,
        operation=operation,
        params=params or {},
        status="pending",
        timeout_seconds=timeout_seconds,
        claim_token="ct_" + secrets.token_urlsafe(24),
    )
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    _try_push(target_device_id, cmd)
    return cmd

def _try_push(device_id: str, cmd: CommandRequest) -> bool:
    from .ws import get_connection_manager
    try:
        loop = get_main_loop()
        if loop is None:
            return False
        manager = get_connection_manager()
        future = asyncio.run_coroutine_threadsafe(
            manager.push_command(device_id, cmd), loop
        )
        return future.result(timeout=2.0)
    except Exception as e:
        log.warning(f"_try_push({device_id}) failed: {e}")
        return False

_main_loop = None

def set_main_loop(loop) -> None:
    global _main_loop
    _main_loop = loop

def get_main_loop():
    return _main_loop


# --- EVENT BUS (SSE) ---

class EventBus:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._last_statuses: dict[str, dict] = {}

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.append(q)
            snapshot = list(self._last_statuses.values())
        for ev in snapshot:
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                break
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    async def publish(self, event: dict) -> None:
        async with self._lock:
            self._last_statuses[event.get("command_id", "")] = event
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

event_bus = EventBus()

def get_event_bus() -> EventBus:
    return event_bus

def publish_command_status(cmd: CommandRequest) -> None:
    event = {
        "type": "command_status",
        "command_id": cmd.id,
        "status": cmd.status,
        "target_device_id": cmd.target_device_id,
        "source_device_id": cmd.source_device_id,
        "operation": cmd.operation,
        "result": cmd.result,
        "error": cmd.error,
        "completed_at": cmd.completed_at.isoformat() if cmd.completed_at else None,
        "claimed_at": cmd.claimed_at.isoformat() if cmd.claimed_at else None,
        "created_at": cmd.created_at.isoformat() if cmd.created_at else None,
    }
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    asyncio.ensure_future(event_bus.publish(event))

def _device_acl_filter(device: Device, event: dict) -> bool:
    if device.is_first_webui_device:
        return True
    return event.get("source_device_id") == device.id or event.get("target_device_id") == device.id

async def _sse_generator(device: Device, queue: asyncio.Queue) -> AsyncIterator[bytes]:
    yield b": connected\n\n"
    loop = asyncio.get_running_loop()
    last_ping = loop.time()
    try:
        while True:
            now = loop.time()
            if now - last_ping > 15.0:
                yield b": keep-alive\n\n"
                last_ping = now
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                if not _device_acl_filter(device, event):
                    continue
                yield f"event: {event.get('type', 'message')}\n".encode()
                yield f"data: {json.dumps(event)}\n\n".encode()
                last_ping = now
            except asyncio.TimeoutError:
                yield b": keep-alive\n\n"
                last_ping = loop.time()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.exception(f"SSE generator error: {e}")

