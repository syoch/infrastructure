"""Typed JSON response shapes for the app-portal REST API.

These ``TypedDict``s describe the dicts built in ``api.py``. Handlers that
return them set ``response_model=None`` so FastAPI does not start validating
against the annotation (preserving the historical ``dict[str, Any]`` behavior).
"""
from typing import NotRequired, TypedDict


class FeedbackDict(TypedDict):
    id: str
    app_id: str
    author: str | None
    body: str
    kind: str
    status: str
    command_id: str | None
    target_session_id: str | None
    webui_url: str | None
    delivered_at: str | None
    error: str | None
    created_at: str | None


class AppDict(TypedDict):
    id: str
    slug: str
    name: str
    description: str | None
    url: str | None
    project_directory: str
    opencode_session_id: str
    bridge_device_id: str
    source: str
    tags: list[str]
    status: str
    webui_url: str | None
    created_at: str | None
    updated_at: str | None
    created_by: str | None
    feedback: NotRequired[list[FeedbackDict]]


class BridgeDict(TypedDict):
    device_id: str
    hostname: str | None
    webui_base_url: str | None
    server_key: str | None
    last_seen: str | None
    registered_at: str | None


class AppListResponse(TypedDict):
    apps: list[AppDict]


class FeedbackListResponse(TypedDict):
    feedback: list[FeedbackDict]


class BridgeListResponse(TypedDict):
    bridges: list[BridgeDict]


class BridgeAnnounceResponse(TypedDict):
    status: str
    device_id: str
    webui_base_url: str | None
    server_key: str | None


class DeleteResponse(TypedDict):
    status: str
    deleted: str
