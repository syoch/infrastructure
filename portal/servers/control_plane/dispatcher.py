import re
import secrets
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from .models import (
    Device, DeviceACL, OperationSpec, CommandRequest,
)


KNOWN_TYPES = {"device"}


def _strip_type_prefix(value: str) -> str:
    if ":" in value:
        type_, pattern = value.split(":", 1)
        return pattern
    return value


def can_issue(db: Session, source_id: str, target_id: str, operation: str) -> bool:
    """
    Returns True iff at least one ACL row matches the (source, target, operation) tuple.
    Matching: source_device regex matches source_id AND target_device regex matches target_id
              AND operation regex matches operation.
    """
    acls = db.query(DeviceACL).all()
    for acl in acls:
        src_match = re.search(_strip_type_prefix(acl.source_device), source_id)
        tgt_match = re.search(_strip_type_prefix(acl.target_device), target_id)
        op_match = re.search(acl.operation, operation)
        if src_match and tgt_match and op_match:
            return True
    return False


def resolve_provider(db: Session, operation_id: str, target_device_id: str) -> Optional[OperationSpec]:
    """
    Returns the OperationSpec for the (operation_id, target_device_id) pair,
    or None if not registered. operation ids are unique per provider.
    """
    return (
        db.query(OperationSpec)
        .filter(OperationSpec.id == operation_id)
        .filter(OperationSpec.provider == f"device:{target_device_id}")
        .first()
    )


def provider_device_id(spec: OperationSpec) -> Optional[str]:
    """
    Extracts the device id from an OperationSpec.provider field ("device:<id>").
    Returns None if the provider is not in the expected format.
    """
    if not spec or not spec.provider.startswith("device:"):
        return None
    return spec.provider.removeprefix("device:")


def filter_operations_for_device(db: Session, device: Device) -> list[OperationSpec]:
    """
    Returns operations visible to the given device.
    - If the device is the first WebUI device, all operations are visible.
    - Otherwise, only operations provided by devices that the current device can issue commands to (per ACL) are visible.
    """
    all_specs = db.query(OperationSpec).all()
    if device.is_first_webui_device:
        return all_specs
    visible = []
    for spec in all_specs:
        target_id = provider_device_id(spec)
        if target_id is None:
            continue
        if can_issue(db, device.id, target_id, spec.id):
            visible.append(spec)
    return visible


def enqueue_command(
    db: Session,
    source_device: Device,
    target_device_id: str,
    operation: str,
    params: dict,
    timeout_seconds: int = 60,
) -> CommandRequest:
    """
    Creates a new CommandRequest in 'pending' status.
    Returns the created command.
    Also attempts to push the command to the target device's WebSocket (if connected).
    """
    cmd = CommandRequest(
        id=str(uuid.uuid4()),
        target_device_id=target_device_id,
        source_device_id=source_device.id,
        operation=operation,
        params=params or {},
        status="pending",
        timeout_seconds=timeout_seconds,
        claim_token=_generate_claim_token(),
    )
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    _try_push(target_device_id, cmd)
    return cmd


def _try_push(device_id: str, cmd: CommandRequest) -> bool:
    """
    Best-effort push of a pending command to the target device's WS.
    Returns True if the command was successfully sent, False otherwise.
    """
    import asyncio
    import logging
    from .ws import get_connection_manager
    log = logging.getLogger("control_plane.dispatcher")
    try:
        loop = get_main_loop()
        if loop is None:
            return False
        manager = get_connection_manager()
        future = asyncio.run_coroutine_threadsafe(
            manager.push_command(device_id, cmd), loop
        )
        return future.result(timeout=2.0)
    except Exception as e:
        log.warning(f"_try_push({device_id}) failed: {e}")
        return False


_main_loop = None


def set_main_loop(loop) -> None:
    global _main_loop
    _main_loop = loop


def get_main_loop():
    return _main_loop


def _generate_claim_token() -> str:
    return "ct_" + secrets.token_urlsafe(24)
