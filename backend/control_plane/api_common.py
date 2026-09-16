from typing import Any

from pydantic import BaseModel, Field, field_validator

from .manager_cli import validate_acl_field, validate_device_id
from .models import (
    Device, DeviceACL, DeviceBootstrapToken, OperationSpec, CommandRequest,
)


def _device_to_dict(d: Device, include_token: bool = False) -> dict[str, Any]:
    res = {
        "id": d.id,
        "display_name": d.display_name,
        "ws_state": d.ws_state,
        "last_seen": d.last_seen.isoformat() + "Z" if d.last_seen else None,
        "registered_at": d.registered_at.isoformat() + "Z" if d.registered_at else None,
        "is_first_webui_device": d.is_first_webui_device,
    }
    if include_token:
        res["bearer_token"] = d.bearer_token
    return res


def _acl_to_dict(a: DeviceACL) -> dict[str, Any]:
    return {
        "id": a.id,
        "source_device": a.source_device,
        "target_device": a.target_device,
        "operation": a.operation,
        "extra": a.extra,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _operation_to_dict(o: OperationSpec) -> dict[str, Any]:
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


def _command_to_dict(c: CommandRequest) -> dict[str, Any]:
    return {
        "id": c.id,
        "target_device_id": c.target_device_id,
        "source_device_id": c.source_device_id,
        "operation": c.operation,
        "params": c.params,
        "status": c.status,
        "created_at": c.created_at,
        "claimed_at": c.claimed_at,
        "completed_at": c.completed_at,
        "result": c.result,
        "error": c.error,
        "timeout_seconds": c.timeout_seconds,
    }


def _token_to_dict(t: DeviceBootstrapToken) -> dict[str, Any]:
    return {
        "id": t.id,
        "device_id": t.device_id,
        "display_name": t.display_name,
        "expires_at": t.expires_at.isoformat() + "Z" if t.expires_at else None,
        "consumed_at": t.consumed_at.isoformat() + "Z" if t.consumed_at else None,
        "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
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
    params: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)

    @field_validator("target_device_id")
    @classmethod
    def _v_target_id(cls, v: str) -> str:
        validate_device_id(v)
        return v


class TokenIssueBody(BaseModel):
    device_id: str
    display_name: str
    ttl_minutes: int = Field(default=15, ge=1, le=1440)

    @field_validator("device_id")
    @classmethod
    def _v_device_id(cls, v: str) -> str:
        validate_device_id(v)
        return v
