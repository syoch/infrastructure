import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncIterator
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from .auth import get_current_device
from .models import Device, CommandRequest
from backend.core.database import get_session


router = APIRouter(prefix="/api/control", tags=["control-plane-sse"])
log = logging.getLogger("control_plane.sse")


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
    """
    Best-effort publish from non-async code. Schedules publish on the running loop.
    """
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
        import asyncio
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if not loop.is_running():
        return
    asyncio.ensure_future(event_bus.publish(event))


def _device_acl_filter(device: Device, cmd: CommandRequest) -> bool:
    if device.is_first_webui_device:
        return True
    return cmd.source_device_id == device.id or cmd.target_device_id == device.id


async def _sse_generator(device: Device, queue: asyncio.Queue) -> AsyncIterator[bytes]:
    yield b": connected\n\n"
    last_ping = asyncio.get_event_loop().time()
    try:
        while True:
            now = asyncio.get_event_loop().time()
            if now - last_ping > 15.0:
                yield b": keep-alive\n\n"
                last_ping = now
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                if not _device_acl_filter(device, _event_to_cmd(event)):
                    continue
                yield f"event: {event.get('type', 'message')}\n".encode()
                yield f"data: {json.dumps(event)}\n\n".encode()
                last_ping = now
            except asyncio.TimeoutError:
                yield b": keep-alive\n\n"
                last_ping = asyncio.get_event_loop().time()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.exception(f"SSE generator error: {e}")


def _event_to_cmd(event: dict) -> CommandRequest:
    return CommandRequest(
        id=event.get("command_id", ""),
        status=event.get("status", "pending"),
        target_device_id=event.get("target_device_id", ""),
        source_device_id=event.get("source_device_id", ""),
        operation=event.get("operation", ""),
    )


@router.get("/events")
async def sse_events(
    request: Request,
    device: Device = Depends(get_current_device),
):
    queue = await event_bus.subscribe()

    async def gen():
        try:
            async for chunk in _sse_generator(device, queue):
                if await request.is_disconnected():
                    break
                yield chunk
        finally:
            await event_bus.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
