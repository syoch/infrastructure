import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from backend.core.database import get_session
from .models import Device, CommandRequest, OperationSpec
from .dispatcher import provider_device_id


router = APIRouter(prefix="/api/control", tags=["control-plane-ws"])
log = logging.getLogger("control_plane.ws")


class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, "WebSocketConnection"] = {}
        self._lock = asyncio.Lock()

    async def register(self, conn: "WebSocketConnection") -> None:
        async with self._lock:
            existing = self.connections.get(conn.device.id)
            if existing is not None and existing is not conn:
                try:
                    await existing.send({"type": "bye", "reason": "replaced_by_new_connection"})
                except Exception:
                    pass
                try:
                    await existing.close()
                except Exception:
                    pass
            self.connections[conn.device.id] = conn

    async def unregister(self, conn: "WebSocketConnection") -> None:
        async with self._lock:
            current = self.connections.get(conn.device.id)
            if current is conn:
                del self.connections[conn.device.id]

    def get(self, device_id: str) -> Optional["WebSocketConnection"]:
        return self.connections.get(device_id)

    async def push_command(self, device_id: str, command: CommandRequest) -> bool:
        conn = self.get(device_id)
        if conn is None:
            return False
        try:
            await conn.send({
                "type": "command",
                "command_id": command.id,
                "operation": command.operation,
                "params": command.params,
                "timeout_seconds": command.timeout_seconds,
                "claim_token": command.claim_token,
                "source_device_id": command.source_device_id,
            })
            return True
        except Exception as e:
            log.warning(f"push_command failed for {device_id}: {e}")
            return False


class WebSocketConnection:
    def __init__(self, websocket: WebSocket, device: Device, session_factory):
        self.websocket = websocket
        self.device = device
        self.session_factory = session_factory
        self._closed = False

    async def send(self, data: dict) -> None:
        if self._closed:
            return
        await self.websocket.send_text(json.dumps(data))

    async def close(self, code: int = 1000, reason: str = "") -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self.websocket.close(code=code, reason=reason)
        except Exception:
            pass


connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    return connection_manager


async def _send_welcome(conn: WebSocketConnection) -> None:
    session: Session = conn.session_factory()
    try:
        pending = (
            session.query(CommandRequest)
            .filter(
                CommandRequest.target_device_id == conn.device.id,
                CommandRequest.status == "pending",
            )
            .order_by(CommandRequest.created_at)
            .all()
        )
        pending_data = [
            {
                "command_id": c.id,
                "operation": c.operation,
                "params": c.params,
                "timeout_seconds": c.timeout_seconds,
                "claim_token": c.claim_token,
                "source_device_id": c.source_device_id,
            }
            for c in pending
        ]
        await conn.send({
            "type": "welcome",
            "device_id": conn.device.id,
            "display_name": conn.device.display_name,
            "is_first_webui_device": conn.device.is_first_webui_device,
            "pending_commands": pending_data,
        })
    finally:
        session.close()


async def _handle_hello(conn: WebSocketConnection, payload: dict) -> None:
    resumed_ids = payload.get("resumed_claimed_ids") or []
    if not resumed_ids:
        return
    session: Session = conn.session_factory()
    try:
        now = datetime.utcnow()
        for cid in resumed_ids:
            cmd = session.query(CommandRequest).filter_by(id=cid).first()
            if not cmd or cmd.target_device_id != conn.device.id:
                continue
            if cmd.status != "claimed":
                continue
            if cmd.claimed_at and (now - cmd.claimed_at) > timedelta(seconds=cmd.timeout_seconds):
                cmd.status = "timeout"
                cmd.completed_at = now
                session.commit()
    finally:
        session.close()


async def _handle_claim(conn: WebSocketConnection, payload: dict) -> None:
    cmd_id = payload.get("command_id")
    claim_token = payload.get("claim_token")
    if not cmd_id or not claim_token:
        await conn.send({"type": "error", "message": "claim requires command_id and claim_token"})
        return
    session: Session = conn.session_factory()
    try:
        cmd = session.query(CommandRequest).filter_by(id=cmd_id).first()
        if not cmd:
            await conn.send({"type": "error", "message": f"command {cmd_id!r} not found"})
            return
        if cmd.target_device_id != conn.device.id:
            await conn.send({"type": "error", "message": "command is not for this device"})
            return
        if cmd.claim_token != claim_token:
            await conn.send({"type": "error", "message": "claim_token mismatch"})
            return
        if cmd.status != "pending":
            await conn.send({"type": "error", "message": f"command is in status {cmd.status!r}, not pending"})
            return
        cmd.status = "claimed"
        cmd.claimed_at = datetime.utcnow()
        session.commit()
        session.refresh(cmd)
        await conn.send({"type": "claimed_ack", "command_id": cmd.id})
        from .sse import publish_command_status
        publish_command_status(cmd)
    finally:
        session.close()


async def _handle_result(conn: WebSocketConnection, payload: dict) -> None:
    cmd_id = payload.get("command_id")
    status = payload.get("status")
    result = payload.get("result")
    error = payload.get("error")
    if not cmd_id:
        await conn.send({"type": "error", "message": "result requires command_id"})
        return
    if status not in ("succeeded", "failed"):
        await conn.send({"type": "error", "message": f"result status must be 'succeeded' or 'failed', got {status!r}"})
        return
    session: Session = conn.session_factory()
    try:
        cmd = session.query(CommandRequest).filter_by(id=cmd_id).first()
        if not cmd:
            await conn.send({"type": "error", "message": f"command {cmd_id!r} not found"})
            return
        if cmd.target_device_id != conn.device.id:
            await conn.send({"type": "error", "message": "command is not for this device"})
            return
        if cmd.status != "claimed":
            await conn.send({"type": "error", "message": f"command is in status {cmd.status!r}, not claimed"})
            return
        cmd.status = status
        cmd.completed_at = datetime.utcnow()
        cmd.result = result
        cmd.error = error
        session.commit()
        session.refresh(cmd)
        await conn.send({"type": "result_ack", "command_id": cmd.id, "status": status})
        from .sse import publish_command_status
        publish_command_status(cmd)
    finally:
        session.close()


async def _handle_operations_register(conn: WebSocketConnection, payload: dict) -> None:
    ops = payload.get("operations") or []
    if not isinstance(ops, list):
        await conn.send({"type": "error", "message": "operations must be a list"})
        return
    session: Session = conn.session_factory()
    try:
        provider = f"device:{conn.device.id}"
        now = datetime.utcnow()
        for op in ops:
            op_id = op.get("id")
            if not op_id or not isinstance(op_id, str):
                continue
            spec = session.query(OperationSpec).filter_by(provider=provider, id=op_id).first()
            if spec is None:
                spec = OperationSpec(
                    id=op_id,
                    provider=provider,
                    group=op.get("group", "default"),
                    name=op.get("name", op_id),
                    description=op.get("description"),
                    params_schema=op.get("params_schema") or {},
                    result_schema=op.get("result_schema"),
                    ui_hint=op.get("ui_hint"),
                    registered_at=now,
                    last_seen=now,
                )
                session.add(spec)
            else:
                spec.group = op.get("group", spec.group)
                spec.name = op.get("name", spec.name)
                if "description" in op:
                    spec.description = op["description"]
                if "params_schema" in op:
                    spec.params_schema = op["params_schema"] or {}
                if "result_schema" in op:
                    spec.result_schema = op["result_schema"]
                if "ui_hint" in op:
                    spec.ui_hint = op["ui_hint"]
                spec.last_seen = now
        session.commit()
        await conn.send({"type": "operations_registered", "count": len(ops)})
    finally:
        session.close()


async def _handle_ping(conn: WebSocketConnection) -> None:
    await conn.send({"type": "pong"})
    session: Session = conn.session_factory()
    try:
        d = session.query(Device).filter_by(id=conn.device.id).first()
        if d:
            d.last_seen = datetime.utcnow()
            session.commit()
    finally:
        session.close()


async def _set_device_ws_state(device_id: str, state: str) -> None:
    session: Session = get_session()
    try:
        d = session.query(Device).filter_by(id=device_id).first()
        if d:
            d.ws_state = state
            d.last_seen = datetime.utcnow()
            session.commit()
    finally:
        session.close()


@router.websocket("/devices/{device_id}/ws")
async def device_ws(
    websocket: WebSocket,
    device_id: str,
    token: str = Query(default=""),
):
    if not token:
        await websocket.close(code=1008, reason="missing token")
        return
    session: Session = get_session()
    try:
        device = session.query(Device).filter_by(id=device_id).first()
        if not device or device.bearer_token != token:
            await websocket.close(code=1008, reason="invalid token")
            return
    finally:
        session.close()

    await websocket.accept()
    conn = WebSocketConnection(websocket, device, get_session)
    await connection_manager.register(conn)
    await _set_device_ws_state(device_id, "online")

    try:
        await _send_welcome(conn)
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await conn.send({"type": "error", "message": "invalid JSON"})
                continue
            mtype = msg.get("type")
            if mtype == "hello":
                await _handle_hello(conn, msg)
            elif mtype == "claim":
                await _handle_claim(conn, msg)
            elif mtype == "result":
                await _handle_result(conn, msg)
            elif mtype == "operations_register":
                await _handle_operations_register(conn, msg)
            elif mtype == "ping":
                await _handle_ping(conn)
            else:
                await conn.send({"type": "error", "message": f"unknown message type: {mtype!r}"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.exception(f"WS error for {device_id}: {e}")
    finally:
        await connection_manager.unregister(conn)
        await _set_device_ws_state(device_id, "offline")


def notify_command(device_id: str, command: CommandRequest) -> None:
    """
    Best-effort push helper for non-async callers (e.g. REST handlers).
    Schedules the push on the running event loop if available.
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    asyncio.ensure_future(connection_manager.push_command(device_id, command))
