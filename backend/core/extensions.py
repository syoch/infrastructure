"""Extension registry: stable IDs mapped to their implementing classes.

Deployment configuration refers to extensions by ID (see `config.EXTENSIONS`),
so module paths can change without touching any config.

Two ways to make an ID resolvable:

* core-native extensions are listed in ``EXTENSION_REGISTRY`` below
  (currently empty; first-party extensions ship as separate distributions);
* distributions register an entry point in the ``portal.extensions`` group,
  e.g. in ``pyproject.toml``::

      [project.entry-points."portal.extensions"]
      hello = "hello_extension.extension:HelloExtension"

The implementing class must declare a matching ``ID`` attribute.

When running from a source checkout without the ``portal`` distribution
installed, the entry-point discovery returns nothing, so the declared entry
points are read from the repo root ``pyproject.toml`` and the corresponding
``extensions/<name>`` directories are added to ``sys.path`` (see
:func:`_repo_local_targets`).
"""
import glob
import importlib
import importlib.metadata
import logging
import os
import sys
import tomllib
from functools import lru_cache
from typing import cast

from backend.extensions.base import BaseExtension

logger = logging.getLogger(__name__)

#: Entry-point group external distributions use to register an extension ID.
ENTRY_POINT_GROUP = "portal.extensions"

#: Core-native extensions keyed by stable ID.
#:
#: First-party extensions are registered through the ``portal.extensions``
#: entry-point group (see the root ``pyproject.toml``); this mapping is kept
#: for future extensions that belong to the core itself.
EXTENSION_REGISTRY: dict[str, str] = {}


def _entry_point_targets() -> dict[str, str]:
    targets: dict[str, str] = {}
    for entry_point in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
        # Entry-point values may carry extras, e.g. "pkg.mod:Class [extra]".
        targets[entry_point.name] = entry_point.value.split("[")[0].strip()
    return targets


def _repo_local_targets() -> dict[str, str]:
    """Discovery fallback for a source checkout without an installed dist.

    Reads the ``portal.extensions`` entry points declared in the repo root
    ``pyproject.toml`` (derived from the file, never hardcoded) and puts every
    ``extensions/<dir>`` on ``sys.path`` so the ``portal_*`` packages import.
    """
    from backend.core import config as core_config

    root = core_config.PORTAL_DIR
    extensions_dir = os.path.join(root, "extensions")
    pyproject = os.path.join(root, "pyproject.toml")
    if not os.path.isdir(extensions_dir) or not os.path.isfile(pyproject):
        return {}

    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        logger.warning("could not read %s for repo-local extension discovery", pyproject)
        return {}

    group = data.get("project", {}).get("entry-points", {}).get(ENTRY_POINT_GROUP, {})
    targets: dict[str, str] = {}
    for name, value in group.items():
        if isinstance(value, str):
            targets[name] = value.split("[")[0].strip()

    for path in sorted(glob.glob(os.path.join(extensions_dir, "*"))):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)

    return targets


@lru_cache(maxsize=1)
def extension_targets() -> dict[str, str]:
    """All known ID -> "module:Class" targets (core-native + entry points)."""
    targets = dict(EXTENSION_REGISTRY)
    discovered = _entry_point_targets()
    if not discovered:
        discovered = _repo_local_targets()
    for name, value in discovered.items():
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
