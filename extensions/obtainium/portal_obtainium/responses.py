"""Typed JSON response shapes for the Obtainium extension REST API.

Handlers returning these ``TypedDict``s set ``response_model=None`` so FastAPI
keeps the historical ``dict[str, Any]`` behavior. Genuinely dynamic payloads
(e.g. the compiled export JSON and the settings map) stay ``dict[str, Any]``.
"""
from typing import Any, TypedDict


class LocalApkDict(TypedDict):
    id: int
    version: str
    architecture: str | None
    file_hash: str


class ObtainiumAppDict(TypedDict):
    id: str
    name: str
    url: str
    overrideSource: str | None
    preferredApkIndex: int | None
    pinned: bool
    categories: list[str]
    allowIdChange: bool
    additionalSettings: dict[str, Any]
    apks: list[LocalApkDict]


class ObtainiumAppsResponse(TypedDict):
    apps: list[ObtainiumAppDict]


class StatusMessageResponse(TypedDict):
    status: str
    message: str


class StatusMessageCountResponse(TypedDict):
    status: str
    message: str
    count: int


class LocalApkUploadResponse(TypedDict):
    status: str
    message: str
    id: int
    file_hash: str
