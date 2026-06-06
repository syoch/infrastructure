import uuid
import secrets
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey, Enum, Text, DateTime, UniqueConstraint, CheckConstraint
)
from sqlalchemy.types import JSON
from backend.core.database import Base

DEVICE_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$"


def _uuid4() -> str:
    return str(uuid.uuid4())


def _bearer_token() -> str:
    return "tk_" + secrets.token_urlsafe(32)


class Device(Base):
    __tablename__ = "ctrl_devices"

    id = Column(String(64), primary_key=True)
    display_name = Column(String(128), nullable=False)
    bearer_token = Column(String(64), nullable=False, unique=True, index=True)
    ws_state = Column(
        Enum("online", "offline", "never_connected", name="ctrl_ws_state"),
        default="never_connected",
        nullable=False,
    )
    last_seen = Column(DateTime, nullable=True)
    extra = Column(Text, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_first_webui_device = Column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Device id={self.id!r} name={self.display_name!r} ws_state={self.ws_state!r}>"


class DeviceACL(Base):
    __tablename__ = "ctrl_device_acls"

    id = Column(String(36), primary_key=True, default=_uuid4)
    source_device = Column(String(256), nullable=False)
    target_device = Column(String(256), nullable=False)
    operation = Column(String(256), nullable=False)
    extra = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_device", "target_device", "operation", name="ctrl_acl_unique"),
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceACL id={self.id!r} source={self.source_device!r} "
            f"target={self.target_device!r} operation={self.operation!r}>"
        )


class CommandRequest(Base):
    __tablename__ = "ctrl_command_requests"

    id = Column(String(36), primary_key=True, default=_uuid4)
    target_device_id = Column(
        String(64),
        ForeignKey("ctrl_devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_device_id = Column(
        String(64),
        ForeignKey("ctrl_devices.id"),
        nullable=False,
        index=True,
    )
    operation = Column(String(64), nullable=False)
    params = Column(JSON, nullable=False, default=dict)
    status = Column(
        Enum(
            "pending", "claimed", "succeeded", "failed", "timeout", "cancelled",
            name="ctrl_cmd_status",
        ),
        default="pending",
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    claimed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    claim_token = Column(String(64), nullable=True)
    timeout_seconds = Column(Integer, default=60, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<CommandRequest id={self.id!r} target={self.target_device_id!r} "
            f"source={self.source_device_id!r} operation={self.operation!r} status={self.status!r}>"
        )


class DeviceBootstrapToken(Base):
    __tablename__ = "ctrl_bootstrap_tokens"

    id = Column(String(36), primary_key=True, default=_uuid4)
    device_id = Column(String(64), nullable=False)
    display_name = Column(String(128), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<DeviceBootstrapToken id={self.id!r} device_id={self.device_id!r} "
            f"expires_at={self.expires_at!r}>"
        )


class OperationSpec(Base):
    __tablename__ = "ctrl_operation_specs"

    provider = Column(String(64), primary_key=True, nullable=False)
    id = Column(String(128), primary_key=True, nullable=False)
    group = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    params_schema = Column(JSON, nullable=False, default=dict)
    result_schema = Column(JSON, nullable=True)
    ui_hint = Column(JSON, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "provider LIKE 'device:%'",
            name="ctrl_opspec_provider_device",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<OperationSpec id={self.id!r} provider={self.provider!r} "
            f"group={self.group!r} name={self.name!r}>"
        )
