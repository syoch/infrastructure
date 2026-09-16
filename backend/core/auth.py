"""Pluggable admin-device authentication for core routes.

The core must not import any extension. Routes that need to authenticate a
control-plane admin device (e.g. backup/restore) resolve the provider through
this registry at request time; the control-plane extension registers it during
``setup()``.
"""
from typing import Any, Callable, Optional

#: Callable(authorization=..., token=..., db=...) -> admin device, raising
#: ``HTTPException`` on authentication/authorization failure.
_admin_device_dependency: Optional[Callable[..., Any]] = None


def set_admin_device_dependency(fn: Callable[..., Any]) -> None:
    """Registers the admin-device dependency (idempotent)."""
    global _admin_device_dependency
    _admin_device_dependency = fn


def get_admin_device_dependency() -> Optional[Callable[..., Any]]:
    """Returns the registered admin-device dependency, if any."""
    return _admin_device_dependency
