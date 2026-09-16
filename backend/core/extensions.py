"""Extension registry: stable IDs mapped to their implementing classes.

Deployment configuration refers to extensions by ID (see `config.EXTENSIONS`),
so module paths can change without touching any config. Add new extensions here
and give the implementing class a matching ``ID`` attribute.
"""
import importlib
from typing import Any, Type

EXTENSION_REGISTRY: dict[str, str] = {
    "storage": "backend.storage:StorageManagerExtension",
    "obtainium": "backend.obtainium:ObtainiumRepoExtension",
    "control-plane": "backend.control_plane:ControlPlaneExtension",
    "app-portal": "backend.app_portal:AppPortalExtension",
}


def known_extension_ids() -> list[str]:
    return sorted(EXTENSION_REGISTRY)


def load_extension_class(extension_id: str) -> Type[Any]:
    target = EXTENSION_REGISTRY.get(extension_id)
    if target is None:
        raise ValueError(
            f"unknown extension id {extension_id!r} "
            f"(known: {', '.join(known_extension_ids())})"
        )
    module_name, _, class_name = target.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)
