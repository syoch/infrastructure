import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from .api_common import (
    DeleteResponse,
    TokenDict,
    TokenIssueBody,
    TokenListResponse,
    _token_to_dict,
)
from .core import require_admin
from .models import Device, DeviceBootstrapToken

router = APIRouter(tags=["control-plane"])


@router.get("/tokens", response_model=None)
def list_tokens(
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TokenListResponse:
    tokens = db.query(DeviceBootstrapToken).order_by(DeviceBootstrapToken.created_at.desc()).all()
    return {"tokens": [_token_to_dict(t) for t in tokens]}


@router.post("/tokens", response_model=None)
def issue_token(
    body: TokenIssueBody,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TokenDict:
    if db.query(Device).filter_by(id=body.device_id).first():
        raise HTTPException(status_code=409, detail=f"device {body.device_id!r} is already registered")

    token_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=body.ttl_minutes)
    tok = DeviceBootstrapToken(
        id=token_id,
        device_id=body.device_id,
        display_name=body.display_name,
        expires_at=expires_at.replace(tzinfo=None), # Store as naive UTC in DB
    )
    db.add(tok)
    db.commit()
    db.refresh(tok)
    return _token_to_dict(tok)


@router.delete("/tokens/{token_id}", response_model=None)
def delete_token(
    token_id: str,
    device: Device = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DeleteResponse:
    tok = db.query(DeviceBootstrapToken).filter_by(id=token_id).first()
    if not tok:
        raise HTTPException(status_code=404, detail="token not found")
    db.delete(tok)
    db.commit()
    return {"status": "success", "deleted": token_id}
