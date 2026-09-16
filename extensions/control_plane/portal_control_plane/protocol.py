"""Wire protocol between the control plane and device agents.

JSON messages exchanged over the device WebSocket. The device agent keeps a
mirrored copy in ``device_agent/protocol.py`` (it must not import the backend).
"""
from typing import Any, Literal, TypedDict


# --- server -> agent -------------------------------------------------------

class PendingCommand(TypedDict):
    command_id: str
    operation: str
    params: dict[str, Any]
    timeout_seconds: int
    claim_token: str
    source_device_id: str


class CommandMessage(TypedDict):
    type: Literal["command"]
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


class ClaimedAckMessage(TypedDict):
    type: Literal["claimed_ack"]
    command_id: str


class ResultAckMessage(TypedDict):
    type: Literal["result_ack"]
    command_id: str
    status: str


class OperationsRegisteredMessage(TypedDict):
    type: Literal["operations_registered"]
    count: int


class ErrorMessage(TypedDict):
    type: Literal["error"]
    message: str


class ByeMessage(TypedDict):
    type: Literal["bye"]
    reason: str


class PongMessage(TypedDict):
    type: Literal["pong"]


# --- agent -> server -------------------------------------------------------

class OperationSpec(TypedDict):
    id: str
    name: str
    group: str


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


# --- derived -----------------------------------------------------------------

class CommandStatusEvent(TypedDict):
    type: Literal["command_status"]
    command_id: str
    status: str
    target_device_id: str
    source_device_id: str
    operation: str
    result: Any
    error: Any
    completed_at: str | None
    claimed_at: str | None
    created_at: str | None


ServerMessage = (
    WelcomeMessage
    | CommandMessage
    | ClaimedAckMessage
    | ResultAckMessage
    | OperationsRegisteredMessage
    | ErrorMessage
    | ByeMessage
    | PongMessage
)

AgentMessage = (
    OperationsRegisterMessage
    | ClaimMessage
    | ResultMessage
    | HelloMessage
)
