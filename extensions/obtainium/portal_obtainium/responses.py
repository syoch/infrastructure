"""Typed JSON response shapes for the Obtainium extension REST API.

The ``TypedDict``s describe the dicts built in ``api.py``; the mirrored Pydantic
``BaseModel``s are used as FastAPI ``response_model``s so the OpenAPI document
gains response schemas. Genuinely dynamic payloads (e.g. the compiled export
JSON and the settings map) stay ``dict[str, Any]`` and remain unmodeled.
"""
from typing import Any, TypedDict

from pydantic import BaseModel


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


class LocalApkOut(BaseModel):
    id: int
    version: str
    architecture: str | None
    file_hash: str


class ObtainiumAppOut(BaseModel):
    id: str
    name: str
    url: str
    overrideSource: str | None
    preferredApkIndex: int | None
    pinned: bool
    categories: list[str]
    allowIdChange: bool
    additionalSettings: dict[str, Any]
    apks: list[LocalApkOut]


class ObtainiumAppsOut(BaseModel):
    apps: list[ObtainiumAppOut]


class StatusMessageOut(BaseModel):
    status: str
    message: str


class StatusMessageCountOut(BaseModel):
    status: str
    message: str
    count: int


class LocalApkUploadOut(BaseModel):
    status: str
    message: str
    id: int
    file_hash: str
