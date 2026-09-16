from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from .api_common import (
    ACLBody,
    ACLDict,
    ACLListOut,
    ACLListResponse,
    ACLOut,
    DeleteOut,
    DeleteResponse,
    _acl_to_dict,
)
from .core import get_current_device, require_admin
from .models import Device, DeviceACL

router = APIRouter(tags=["control-plane"])


@router.get("/acls", response_model=ACLListOut)
def list_acls(
    device: Device = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> ACLListResponse:
    acls = db.query(DeviceACL).order_by(DeviceACL.created_at).all()
    return {"acls": [_acl_to_dict(a) for a in acls]}


@router.post("/acls", response_model=ACLOut)
def create_acl(
    body: ACLBody,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ACLDict:
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


@router.patch("/acls/{acl_id}", response_model=ACLOut)
def update_acl(
    acl_id: str,
    body: ACLBody,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ACLDict:
    acl = db.query(DeviceACL).filter_by(id=acl_id).first()
    if not acl:
        raise HTTPException(status_code=404, detail=f"ACL {acl_id!r} not found")
    acl.source_device = body.source_device
    acl.target_device = body.target_device
    acl.operation = body.operation
    db.commit()
    db.refresh(acl)
    return _acl_to_dict(acl)


@router.delete("/acls/{acl_id}", response_model=DeleteOut)
def delete_acl(
    acl_id: str,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DeleteResponse:
    acl = db.query(DeviceACL).filter_by(id=acl_id).first()
    if not acl:
        raise HTTPException(status_code=404, detail=f"ACL {acl_id!r} not found")
    db.delete(acl)
    db.commit()
    return {"status": "success", "deleted": acl_id}
