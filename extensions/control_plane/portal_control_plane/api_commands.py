from collections.abc import AsyncIterator
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.core.database import get_db
from .api_common import (
    CommandBody,
    CommandDict,
    CommandListResponse,
    OperationDict,
    OperationListResponse,
    _command_to_dict,
    _operation_to_dict,
)
from .core import (
    get_current_device,
    can_issue,
    resolve_provider,
    provider_device_id,
    filter_operations_for_device,
    enqueue_command,
    event_bus,
    _sse_generator,
)
from .models import Device, CommandRequest

router = APIRouter(tags=["control-plane"])


@router.get("/events")
async def sse_events(
    request: Request,
    device: Device = Depends(get_current_device),
) -> StreamingResponse:
    queue = await event_bus.subscribe()

    async def gen() -> AsyncIterator[bytes]:
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


@router.get("/operations", response_model=None)
def list_operations(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> OperationListResponse:
    visible = filter_operations_for_device(db, device)
    return {"operations": [_operation_to_dict(o) for o in visible]}


@router.post("/commands", response_model=None)
def create_command(
    body: CommandBody,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> CommandDict:
    target = db.query(Device).filter_by(id=body.target_device_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"target device {body.target_device_id!r} not found")
    if not can_issue(db, device.id, body.target_device_id, body.operation):
        raise HTTPException(
            status_code=403,
            detail=f"no ACL grants source={device.id!r} target={body.target_device_id!r} operation={body.operation!r}",
        )
    spec = resolve_provider(db, body.operation, body.target_device_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"operation {body.operation!r} not registered for device {body.target_device_id!r}")
    provider_id = provider_device_id(spec)
    if provider_id != body.target_device_id:
        raise HTTPException(
            status_code=400,
            detail=f"operation {body.operation!r} is provided by {spec.provider!r}, not {body.target_device_id!r}",
        )
    cmd = enqueue_command(
        db,
        source_device=device,
        target_device_id=body.target_device_id,
        operation=body.operation,
        params=body.params,
        timeout_seconds=body.timeout_seconds,
    )
    return _command_to_dict(cmd)


@router.get("/commands", response_model=None)
def list_commands(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = None,
    op: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
) -> CommandListResponse:
    valid_statuses = {"pending", "claimed", "succeeded", "failed", "timeout", "cancelled"}
    if status is not None and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"invalid status {status!r}, must be one of {sorted(valid_statuses)}",
        )
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    q = db.query(CommandRequest)
    if status is not None:
        q = q.filter(CommandRequest.status == status)
    if from_ is not None:
        q = q.filter(CommandRequest.created_at >= from_)
    if to is not None:
        q = q.filter(CommandRequest.created_at <= to)
    if op:
        q = q.filter(CommandRequest.operation.like(f"%{op}%"))

    total = q.count()
    rows = (
        q.order_by(CommandRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "commands": [_command_to_dict(c) for c in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/commands/{command_id}", response_model=None)
def get_command(
    command_id: str,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> CommandDict:
    cmd = db.query(CommandRequest).filter_by(id=command_id).first()
    if not cmd:
        raise HTTPException(status_code=404, detail=f"command {command_id!r} not found")
    if cmd.source_device_id != device.id and not device.is_first_webui_device:
        raise HTTPException(status_code=403, detail="not allowed to view this command")
    return _command_to_dict(cmd)
