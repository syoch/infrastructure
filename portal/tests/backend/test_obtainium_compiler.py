#!/usr/bin/env python3
"""Unit tests for the self-hosted APK regex generation in ObtainiumConfigCompiler.

Obtainium applies apkFilterRegEx and versionExtractionRegEx to the *absolute
download URL* (not the bare filename), so these must match the full URL. This
guards against regressions such as anchoring (^...$) or filename-only regexes,
which surface on devices as "No suitable release found".
"""
import json
import os
import re
import sys
from types import SimpleNamespace

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

from servers.obtainium_repo.compiler import ObtainiumConfigCompiler


def _compiler():
    # _build_app does not touch the DB; a bare config object is enough.
    cfg = SimpleNamespace(PORTAL_DIR=PORTAL_DIR, DEFAULT_PORT=8000)
    return ObtainiumConfigCompiler(cfg)


def _self_hosted_app(app_id, name, apks):
    return SimpleNamespace(
        id=app_id,
        name=name,
        url=f"{app_id}.example",
        override_source=None,
        additional_settings={},
        preferred_apk_index=None,
        pinned=False,
        allow_id_change=False,
        categories=[],
        apks=[
            SimpleNamespace(id=a["id"], version=a["version"],
                            architecture=a.get("arch"), file_hash="h")
            for a in apks
        ],
    )


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _check_self_hosted(app_id, name, apks, base="https://portal.syoch.org"):
    app = _self_hosted_app(app_id, name, apks)
    export = _compiler()._build_app(app, base)

    additional = json.loads(export["additionalSettings"])
    flt = additional["apkFilterRegEx"]
    ver = additional["versionExtractionRegEx"]
    group = additional["matchGroupToUse"]

    urls = json.loads(export["apkUrls"])
    _assert(len(urls) == 1, f"unexpected apkUrls: {urls}")
    filename, url = urls[0]
    _assert(url.startswith(f"{base}/api/apps/download/"),
            f"unexpected download url: {url}")

    _assert(isinstance(group, str), f"matchGroupToUse must be a string, got {group!r}")
    _assert(re.search(flt, url), f"apkFilterRegEx {flt!r} did not match {url!r}")

    m = re.search(ver, url)
    _assert(m is not None, f"versionExtractionRegEx {ver!r} did not match {url!r}")
    version = m.group(int(group))
    _assert(version == apks[-1]["version"],
            f"extracted {version!r}, expected {apks[-1]['version']!r} (url {url!r})")
    _assert(filename in url, f"filename {filename!r} not in url {url!r}")
    return url, flt, ver, version


def run_all():
    print("=" * 60)
    print("      Obtainium compiler: self-hosted APK regex tests")
    print("=" * 60)

    print("\n[regex] single arch version 1.0.7")
    url, flt, ver, v = _check_self_hosted(
        "com.Arke12917.Arcaoid", "Arcaoid",
        [{"id": 12, "version": "1.0.7", "arch": "arm64-v8a"}],
    )
    print(f"  -> {v!r} from {url}")

    print("\n[regex] version already prefixed with 'v'")
    _check_self_hosted(
        "com.foo.bar", "My App",
        [{"id": 3, "version": "v2.3.4", "arch": None}],
    )
    print("  -> OK")

    print("\n[regex] multiple architectures")
    _check_self_hosted(
        "com.foo", "Foo",
        [
            {"id": 4, "version": "1.2", "arch": "arm64-v8a"},
            {"id": 5, "version": "1.2", "arch": "armeabi-v7a"},
        ],
    )
    print("  -> OK")

    print("\n[regex] regex-special package id + name characters")
    _check_self_hosted(
        "jp.co.example.a+b", "A+B App (Beta)",
        [{"id": 9, "version": "r12", "arch": "x86_64"}],
    )
    print("  -> OK")

    print("\n[regex] filter must not match a different app")
    _, flt, _, _ = _check_self_hosted(
        "com.foo", "Foo", [{"id": 1, "version": "1.0", "arch": None}],
    )
    other = "https://portal.syoch.org/api/apps/download/9/Bar_com.foo.bar_v1.0.apk"
    _assert(not re.search(flt, other),
            f"apkFilterRegEx {flt!r} unexpectedly matched {other!r}")
    print("  -> OK")

    print("\n" + "=" * 60)
    print("      ALL OBTAINIUM COMPILER TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
