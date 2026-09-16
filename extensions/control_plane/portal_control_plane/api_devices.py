from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from .api_common import (
    DeleteResponse,
    DeviceDict,
    DeviceListResponse,
    RegisterDeviceBody,
    RenameDeviceBody,
    _device_to_dict,
)
from .core import get_current_device, require_admin
from .manager_cli import validate_device_id
from .models import Device, DeviceBootstrapToken
from backend.utils.tokens import generate_bearer_token

router = APIRouter(tags=["control-plane"])


@router.get("/devices", response_model=None)
def list_devices(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> DeviceListResponse:
    devices = db.query(Device).order_by(Device.registered_at).all()
    return {"devices": [_device_to_dict(d) for d in devices]}


@router.get("/devices/me", response_model=None)
def get_me(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> DeviceDict:
    return _device_to_dict(device, include_token=True)


@router.patch("/devices/{device_id}", response_model=None)
def rename_device(
    device_id: str,
    body: RenameDeviceBody,
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> DeviceDict:
    validate_device_id(device_id)
    if device.id != device_id and not device.is_first_webui_device:
        raise HTTPException(status_code=403, detail="admin privilege required to rename other devices")
    target = db.query(Device).filter_by(id=device_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"device {device_id!r} not found")
    target.display_name = body.display_name
    db.commit()
    return _device_to_dict(target)


@router.delete("/devices/{device_id}", response_model=None)
def delete_device(
    device_id: str,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DeleteResponse:
    validate_device_id(device_id)
    target = db.query(Device).filter_by(id=device_id).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"device {device_id!r} not found")
    if target.id == device.id:
        raise HTTPException(status_code=400, detail="cannot delete the admin device via API; use CLI to clear admin first")
    db.delete(target)
    db.commit()
    return {"status": "success", "deleted": device_id}


@router.post("/devices/{device_id}/set-admin", response_model=None)
def set_admin(
    device_id: str,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DeviceDict:
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


@router.post("/devices/register", response_model=None)
def register_device(
    body: RegisterDeviceBody,
    db: Session = Depends(get_db),
) -> DeviceDict:
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
