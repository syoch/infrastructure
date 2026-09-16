"""Extension registry: stable IDs mapped to their implementing classes.

Deployment configuration refers to extensions by ID (see `config.EXTENSIONS`),
so module paths can change without touching any config.

Two ways to make an ID resolvable:

* first-party extensions are listed in ``EXTENSION_REGISTRY`` below;
* external distributions register an entry point in the
  ``portal.extensions`` group, e.g. in ``pyproject.toml``::

      [project.entry-points."portal.extensions"]
      hello = "hello_extension.extension:HelloExtension"

The implementing class must declare a matching ``ID`` attribute.
"""
import importlib
import importlib.metadata
import logging
from functools import lru_cache
from typing import cast

from backend.extensions.base import BaseExtension

logger = logging.getLogger(__name__)

#: Entry-point group external distributions use to register an extension ID.
ENTRY_POINT_GROUP = "portal.extensions"

EXTENSION_REGISTRY: dict[str, str] = {
    "storage": "backend.storage:StorageManagerExtension",
    "obtainium": "backend.obtainium:ObtainiumRepoExtension",
    "control-plane": "backend.control_plane:ControlPlaneExtension",
    "app-portal": "backend.app_portal:AppPortalExtension",
}


def _entry_point_targets() -> dict[str, str]:
    targets: dict[str, str] = {}
    for entry_point in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
        # Entry-point values may carry extras, e.g. "pkg.mod:Class [extra]".
        targets[entry_point.name] = entry_point.value.split("[")[0].strip()
    return targets


@lru_cache(maxsize=1)
def extension_targets() -> dict[str, str]:
    """All known ID -> "module:Class" targets (first-party + entry points)."""
    targets = dict(EXTENSION_REGISTRY)
    for name, value in _entry_point_targets().items():
        if name in targets:
            logger.warning(
                "external extension %r overrides the built-in target %r",
                name,
                targets[name],
            )
        targets[name] = value
    return targets


def known_extension_ids() -> list[str]:
    return sorted(extension_targets())


def load_extension_class(extension_id: str) -> type[BaseExtension]:
    target = extension_targets().get(extension_id)
    if target is None:
        raise ValueError(
            f"unknown extension id {extension_id!r} "
            f"(known: {', '.join(known_extension_ids())})"
        )
    module_name, _, class_name = target.partition(":")
    module = importlib.import_module(module_name)
    return cast(type[BaseExtension], getattr(module, class_name))
