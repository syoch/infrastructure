from datetime import datetime
from fastapi import Header, Query, HTTPException, Depends, status
from sqlalchemy.orm import Session
from backend.core.database import get_db
from .models import Device


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
    """
    Resolves the current device from the Authorization header or ?token= query param.
    """
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
    """
    Like get_current_device, but if no device has is_first_webui_device=True yet,
    promote the current device to be the first WebUI device.
    """
    has_admin = db.query(Device).filter(Device.is_first_webui_device == True).first()
    if has_admin is None:
        device.is_first_webui_device = True
        device.last_seen = datetime.utcnow()
        db.commit()
        db.refresh(device)
    else:
        device.last_seen = datetime.utcnow()
        db.commit()
        db.refresh(device)
    return device


def require_admin(device: Device = Depends(get_current_device)) -> Device:
    """
    Dependency that requires the current device to be the first WebUI device.
    """
    if not device.is_first_webui_device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin privilege required (this device is not the first WebUI device)",
        )
    return device
