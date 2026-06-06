import re
import secrets
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from backend.core.database import get_db
from .auth import (
    get_current_device,
    get_current_device_with_promotion,
    require_admin,
)
from .dispatcher import (
    can_issue,
    resolve_provider,
    provider_device_id,
    filter_operations_for_device,
    enqueue_command,
)
from .models import (
    Device, DeviceACL, DeviceBootstrapToken, OperationSpec, CommandRequest,
)
from .manager_cli import (
    validate_acl_field, validate_device_id, generate_bearer_token, _strip_type_prefix, KNOWN_TYPES,
)


router = APIRouter(prefix="/api/control", tags=["control-plane"])


def _device_to_dict(d: Device, include_token: bool = False) -> dict:
    data = {
        "id": d.id,
        "display_name": d.display_name,
        "ws_state": d.ws_state,
        "is_first_webui_device": d.is_first_webui_device,
        "last_seen": d.last_seen.isoformat() if d.last_seen else None,
        "registered_at": d.registered_at.isoformat() if d.registered_at else None,
    }
    if include_token:
        data["bearer_token"] = d.bearer_token
    return data


def _acl_to_dict(a: DeviceACL) -> dict:
    return {
        "id": a.id,
        "source_device": a.source_device,
        "target_device": a.target_device,
        "operation": a.operation,
        "extra": a.extra,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _operation_to_dict(o: OperationSpec) -> dict:
    return {
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


def _command_to_dict(c: CommandRequest) -> dict:
    return {
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
        "timeout_seconds": c.timeout_seconds,
    }


class RegisterDeviceBody(BaseModel):
    device_id: str
    display_name: str
    bootstrap_token: str

    @field_validator("device_id")
    @classmethod
    def _v_device_id(cls, v: str) -> str:
        validate_device_id(v)
        return v


class RenameDeviceBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)


class ACLBody(BaseModel):
    source_device: str
    target_device: str
    operation: str

    @field_validator("source_device", "target_device")
    @classmethod
    def _v_acl_field_with_prefix(cls, v: str) -> str:
        validate_acl_field("field", v, require_prefix=True)
        return v

    @field_validator("operation")
    @classmethod
    def _v_operation(cls, v: str) -> str:
        validate_acl_field("operation", v, require_prefix=False)
        return v


class CommandBody(BaseModel):
    target_device_id: str
    operation: str
    params: dict = Field(default_factory=dict)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)

    @field_validator("target_device_id")
    @classmethod
    def _v_target_id(cls, v: str) -> str:
        validate_device_id(v)
        return v


@router.get("/devices")
def list_devices(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
):
    devices = db.query(Device).order_by(Device.registered_at).all()
    return {"devices": [_device_to_dict(d) for d in devices]}


@router.get("/devices/me")
def get_me(
    device: Device = Depends(get_current_device_with_promotion),
    db: Session = Depends(get_db),
):
    return _device_to_dict(device, include_token=True)


@router.patch("/devices/{device_id}")
def rename_device(
    device_id: str,
    body: RenameDeviceBody,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
):
    validate_device_id(device_id)
    if device.id != device_id and not device.is_first_webui_device:
        raise HTTPException(status_code=403, detail="admin privilege required to rename other devices")
    target = db.query(Device).filter_by(id=device_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"device {device_id!r} not found")
    target.display_name = body.display_name
    db.commit()
    return _device_to_dict(target)


@router.delete("/devices/{device_id}")
def delete_device(
    device_id: str,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_device_id(device_id)
    target = db.query(Device).filter_by(id=device_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"device {device_id!r} not found")
    if target.id == device.id:
        raise HTTPException(status_code=400, detail="cannot delete the admin device via API; use CLI to clear admin first")
    db.delete(target)
    db.commit()
    return {"status": "success", "deleted": device_id}


@router.post("/devices/{device_id}/set-admin")
def set_admin(
    device_id: str,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_device_id(device_id)
    target = db.query(Device).filter_by(id=device_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"device {device_id!r} not found")
    db.query(Device).filter(Device.is_first_webui_device == True).update(
        {"is_first_webui_device": False}
    )
    target.is_first_webui_device = True
    db.commit()
    return _device_to_dict(target)


@router.post("/devices/register")
def register_device(
    body: RegisterDeviceBody,
    db: Session = Depends(get_db),
):
    tok = db.query(DeviceBootstrapToken).filter_by(id=body.bootstrap_token).first()
    if not tok:
        raise HTTPException(status_code=404, detail="bootstrap token not found")
    if tok.consumed_at is not None:
        raise HTTPException(status_code=410, detail="bootstrap token already consumed")
    if tok.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="bootstrap token expired")
    if tok.device_id != body.device_id:
        raise HTTPException(
            status_code=400,
            detail=f"device_id mismatch: token was issued for {tok.device_id!r}, got {body.device_id!r}",
        )
    if db.query(Device).filter_by(id=body.device_id).first():
        raise HTTPException(status_code=409, detail=f"device {body.device_id!r} already registered")
    device = Device(
        id=body.device_id,
        display_name=body.display_name,
        bearer_token=generate_bearer_token(),
        ws_state="never_connected",
        is_first_webui_device=False,
    )
    db.add(device)
    tok.consumed_at = datetime.utcnow()
    db.commit()
    db.refresh(device)
    return _device_to_dict(device, include_token=True)


@router.get("/acls")
def list_acls(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
):
    acls = db.query(DeviceACL).order_by(DeviceACL.created_at).all()
    return {"acls": [_acl_to_dict(a) for a in acls]}


@router.post("/acls")
def create_acl(
    body: ACLBody,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(DeviceACL).filter_by(
        source_device=body.source_device,
        target_device=body.target_device,
        operation=body.operation,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"ACL already exists: {existing.id}")
    acl = DeviceACL(
        source_device=body.source_device,
        target_device=body.target_device,
        operation=body.operation,
    )
    db.add(acl)
    db.commit()
    db.refresh(acl)
    return _acl_to_dict(acl)


@router.patch("/acls/{acl_id}")
def update_acl(
    acl_id: str,
    body: ACLBody,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
):
    acl = db.query(DeviceACL).filter_by(id=acl_id).first()
    if not acl:
        raise HTTPException(status_code=404, detail=f"ACL {acl_id!r} not found")
    acl.source_device = body.source_device
    acl.target_device = body.target_device
    acl.operation = body.operation
    db.commit()
    db.refresh(acl)
    return _acl_to_dict(acl)


@router.delete("/acls/{acl_id}")
def delete_acl(
    acl_id: str,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
):
    acl = db.query(DeviceACL).filter_by(id=acl_id).first()
    if not acl:
        raise HTTPException(status_code=404, detail=f"ACL {acl_id!r} not found")
    db.delete(acl)
    db.commit()
    return {"status": "success", "deleted": acl_id}


@router.get("/operations")
def list_operations(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
):
    visible = filter_operations_for_device(db, device)
    return {"operations": [_operation_to_dict(o) for o in visible]}


@router.post("/commands")
def create_command(
    body: CommandBody,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
):
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


@router.get("/commands")
def list_commands(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    limit = max(1, min(limit, 200))
    rows = (
        db.query(CommandRequest)
        .order_by(CommandRequest.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"commands": [_command_to_dict(c) for c in rows]}


@router.get("/commands/{command_id}")
def get_command(
    command_id: str,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
):
    cmd = db.query(CommandRequest).filter_by(id=command_id).first()
    if not cmd:
        raise HTTPException(status_code=404, detail=f"command {command_id!r} not found")
    if cmd.source_device_id != device.id and not device.is_first_webui_device:
        raise HTTPException(status_code=403, detail="not allowed to view this command")
    return _command_to_dict(cmd)
