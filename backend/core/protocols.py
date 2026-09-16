"""Structural protocols for cross-extension service interfaces."""
from typing import Optional, Protocol

from backend.extensions.base import BaseExtension


class StorageProvider(Protocol):
    """Content-addressable storage provider (implemented by the storage extension)."""

    def save_file(self, file_content: bytes) -> str:
        """Stores bytes and returns the content hash."""
        ...

    def get_file_path(self, file_hash: str) -> str:
        """Returns the absolute path of a stored file."""
        ...

    def delete_file(self, file_hash: str) -> bool:
        """Deletes a stored file if present; returns whether it was removed."""
        ...


class ExtensionHostProtocol(Protocol):
    """Service locator that extensions use to find one another."""

    def get_extension(
        self, name: Optional[str] = None, tags: Optional[list[str]] = None
    ) -> BaseExtension:
        ...

    def all_extensions(self) -> list[BaseExtension]:
        ...
