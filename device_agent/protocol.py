"""Wire protocol with the control plane (mirror of extensions/control_plane/portal_control_plane/protocol.py).

Kept local so the device agent stays a standalone package with no backend
dependency.
"""
from typing import Any, Literal, TypedDict


class PendingCommand(TypedDict):
    command_id: str
    operation: str
    params: dict[str, Any]
    timeout_seconds: int
    claim_token: str
    source_device_id: str


class WelcomeMessage(TypedDict):
    type: Literal["welcome"]
    device_id: str
    display_name: str
    is_first_webui_device: bool
    pending_commands: list[PendingCommand]


class CommandMessage(TypedDict):
    type: Literal["command"]
    command_id: str
    operation: str
    params: dict[str, Any]
    timeout_seconds: int
    claim_token: str
    source_device_id: str


class PingMessage(TypedDict):
    type: Literal["ping"]


class ByeMessage(TypedDict):
    type: Literal["bye"]
    reason: str


class ErrorMessage(TypedDict):
    type: Literal["error"]
    message: str


class ClaimedAckMessage(TypedDict):
    type: Literal["claimed_ack"]
    command_id: str


class OperationsRegisteredMessage(TypedDict):
    type: Literal["operations_registered"]
    count: int


# --- agent -> server -------------------------------------------------------

class OperationsRegisterMessage(TypedDict):
    type: Literal["operations_register"]
    operations: list[dict[str, Any]]


class ClaimMessage(TypedDict):
    type: Literal["claim"]
    command_id: str
    claim_token: str


class ResultMessage(TypedDict):
    type: Literal["result"]
    command_id: str
    status: str
    result: Any
    error: Any


class HelloMessage(TypedDict):
    type: Literal["hello"]
    resumed_claimed_ids: list[str]


class PongMessage(TypedDict):
    type: Literal["pong"]
