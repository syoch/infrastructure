"""Typed JSON response shapes for the app-portal REST API.

These ``TypedDict``s describe the dicts built in ``api.py``, while the mirrored
Pydantic ``BaseModel``s below are used as FastAPI ``response_model``s so the
OpenAPI document gains response schemas. Conditional keys (``NotRequired``) are
declared with a default so routes that omit them keep omitting them when
``response_model_exclude_unset=True`` is set.
"""
from typing import NotRequired, TypedDict

from pydantic import BaseModel


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


class FeedbackOut(BaseModel):
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


class AppOut(BaseModel):
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
    feedback: list[FeedbackOut] | None = None


class BridgeOut(BaseModel):
    device_id: str
    hostname: str | None
    webui_base_url: str | None
    server_key: str | None
    last_seen: str | None
    registered_at: str | None


class AppListOut(BaseModel):
    apps: list[AppOut]


class FeedbackListOut(BaseModel):
    feedback: list[FeedbackOut]


class BridgeListOut(BaseModel):
    bridges: list[BridgeOut]


class BridgeAnnounceOut(BaseModel):
    status: str
    device_id: str
    webui_base_url: str | None
    server_key: str | None


class DeleteOut(BaseModel):
    status: str
    deleted: str
