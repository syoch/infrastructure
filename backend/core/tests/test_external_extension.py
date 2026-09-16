#!/usr/bin/env python3
"""Tests for out-of-tree extension discovery via entry points.

An external distribution registers an extension ID in the ``portal.extensions``
entry-point group; the loader must resolve it without any repo change. This
test fakes a distribution's entry point and a temporary module on sys.path.
"""
import importlib
import importlib.metadata as metadata
import os
import sys
import tempfile
from types import SimpleNamespace

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

from backend.core import extensions  # noqa: E402


FAKE_MODULE = '''
from backend.extensions.base import BaseExtension


class FakeHello(BaseExtension):
    ID = "hello"

    def __init__(self, core_config, ext_config=None):
        super().__init__(core_config)
        self.ext_config = ext_config or {}
        self.tags = ["greeting"]
'''


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _install_fake_entry_point(tmp_dir: str):
    with open(os.path.join(tmp_dir, "fake_hello.py"), "w") as f:
        f.write(FAKE_MODULE)
    return SimpleNamespace(name="hello", value="fake_hello:FakeHello")


def run_all():
    print("=" * 60)
    print("      External extension (entry point) discovery tests")
    print("=" * 60)

    real_entry_points = metadata.entry_points
    real_path = list(sys.path)
    tmp_dir = tempfile.mkdtemp(prefix="portal-ext-test-")
    try:
        fake = _install_fake_entry_point(tmp_dir)
        metadata.entry_points = lambda **kwargs: [fake]
        sys.path.insert(0, tmp_dir)
        importlib.invalidate_caches()
        extensions.extension_targets.cache_clear()

        print("\n[discovery] external id is listed")
        ids = extensions.known_extension_ids()
        _assert("hello" in ids, f"external id missing from {ids}")
        _assert("obtainium" in ids, f"built-in id missing from {ids}")
        print(f"  -> ids include hello: {ids}")

        print("\n[discovery] external class resolves")
        cls = extensions.load_extension_class("hello")
        _assert(cls.__name__ == "FakeHello", f"unexpected class {cls!r}")
        print(f"  -> {cls.__module__}.{cls.__name__}")

        print("\n[discovery] instantiation with per-extension config")
        instance = cls(object(), {"greeting": "hi"})
        _assert(instance.ID == "hello", "ID mismatch")
        _assert(instance.ext_config == {"greeting": "hi"}, "config not passed")
        _assert(instance.tags == ["greeting"], "tags mismatch")
        print("  -> OK")

        print("\n[discovery] unknown id still fails")
        try:
            extensions.load_extension_class("does-not-exist")
        except ValueError as e:
            _assert("unknown extension id" in str(e), f"unexpected error: {e}")
            print(f"  -> ValueError: {e}")
        else:
            raise AssertionError("unknown id did not raise")
    finally:
        metadata.entry_points = real_entry_points
        sys.path[:] = real_path
        extensions.extension_targets.cache_clear()

    print("\n" + "=" * 60)
    print("      ALL EXTERNAL EXTENSION TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
