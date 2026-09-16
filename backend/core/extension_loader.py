import logging
import sys
from typing import Any, Optional

from backend.core.extensions import load_extension_class
from backend.extensions.base import BaseExtension

logger = logging.getLogger(__name__)


class ExtensionHost:
    """
    Registry host that acts as the service locator for loaded extensions.
    Extensions are keyed by their stable ID and can also be looked up by tag.
    """
    def __init__(self, extensions_dict: dict[str, BaseExtension]) -> None:
        self._extensions = extensions_dict

    def get_extension(self, name: Optional[str] = None, tags: Optional[list[str]] = None) -> BaseExtension:
        if not name and not tags:
            raise ValueError("Either extension name or tags must be specified.")
        tags = tags or []

        if name:
            ext = self._extensions.get(name)
            if not ext:
                raise ValueError(f"Required extension '{name}' is not loaded.")
            if tags:
                ext_tags = getattr(ext, "tags", [])
                for tag in tags:
                    if tag not in ext_tags:
                        raise ValueError(f"Extension '{name}' does not implement the required tag '{tag}'.")
            return ext

        # Match purely by tags
        matched_exts: list[BaseExtension] = []
        for ext in self._extensions.values():
            ext_tags = getattr(ext, "tags", [])
            if all(tag in ext_tags for tag in tags):
                matched_exts.append(ext)

        if not matched_exts:
            raise ValueError(f"No loaded extension implements all required tags: {tags}")
        if len(matched_exts) > 1:
            logger.warning(
                "Multiple extensions match tags %s. Resolving to the first loaded: %s",
                tags,
                matched_exts[0].__class__.__name__,
            )
        return matched_exts[0]


def load_extensions(core_config: Any, host: Optional[ExtensionHost] = None) -> list[BaseExtension]:
    """
    Loads the extensions listed in ``core_config.EXTENSIONS`` by ID.

    Each entry is either ``"<id>"`` or ``{"id": "<id>", "config": {...}}``.
    Unknown or duplicate IDs abort startup.
    """
    if core_config.PORTAL_DIR not in sys.path:
        sys.path.insert(0, core_config.PORTAL_DIR)
    if core_config.ROOT_DIR not in sys.path:
        sys.path.insert(0, core_config.ROOT_DIR)

    loaded: dict[str, BaseExtension] = {}
    extensions: list[BaseExtension] = []

    for entry in getattr(core_config, "EXTENSIONS", []):
        extension_id: Optional[str]
        ext_config: dict[str, Any]
        if isinstance(entry, str):
            extension_id, ext_config = entry, {}
        else:
            extension_id = entry.get("id")
            ext_config = entry.get("config") or {}
        if not extension_id:
            raise ValueError(f"extension entry is missing an id: {entry!r}")
        if extension_id in loaded:
            raise ValueError(f"duplicate extension id {extension_id!r}")

        try:
            ext_class = load_extension_class(extension_id)
        except (ImportError, AttributeError) as e:
            raise ValueError(
                f"failed to import extension {extension_id!r}: {e}"
            ) from e

        declared_id = getattr(ext_class, "ID", None)
        if declared_id != extension_id:
            logger.warning(
                "extension %s declares ID %r; registry id is %r",
                ext_class.__name__,
                declared_id,
                extension_id,
            )

        ext_instance = ext_class(core_config, ext_config)
        extensions.append(ext_instance)
        loaded[extension_id] = ext_instance
        logger.info("Loaded extension: %s (%s)", extension_id, ext_class.__name__)

    core_config.LOADED_EXTENSIONS = loaded
    if host is None:
        host = ExtensionHost(loaded)
    core_config.EXTENSION_HOST = host

    for ext in extensions:
        ext.host = host

    return extensions
