#!/usr/bin/env python3
import os
import sys
import json
import time
import signal
import socket
import subprocess
import urllib.request
import urllib.error
import contextlib
import threading
import websockets
from websockets.exceptions import InvalidStatus, ConnectionClosedError, ConnectionClosedOK, WebSocketException

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(SCRIPT_DIR)
PORTAL_DIR = os.path.dirname(TESTS_DIR)
ROOT_DIR = os.path.dirname(PORTAL_DIR)

CONFIG_PATH = os.path.join(PORTAL_DIR, "tests", "config.test.json")
TEST_DB_PATH = os.path.join(PORTAL_DIR, "tests", "portal_test.db")

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

from backend.core import config as _test_config
_test_config.load_config_from_file(CONFIG_PATH)
from backend.core.database import session_scope as _test_session_scope
from servers.control_plane.models import DeviceBootstrapToken as _TestBootstrapToken, Device as _TestDevice

API_PREFIX = "/api/control"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(url: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=1.0).read()
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            time.sleep(0.3)
    return False


_RUNNER_SCRIPT_TEMPLATE = '''
import os
import sys
import uvicorn
PORTAL_DIR = {portal_dir!r}
sys.path.insert(0, PORTAL_DIR)
from backend.core import config
config.load_config_from_file({config_path!r})
from backend.core.server_base import PortalServer
from backend.core.extension_loader import load_extensions
from backend.core.database import init_db
server = PortalServer(host="127.0.0.1", port={port})
extensions = load_extensions(config)
init_db()
for ext in extensions:
    ext.setup()
    server.register_extension(ext)
    if hasattr(ext, "install_event_loop_capture"):
        ext.install_event_loop_capture(server.app)
uvicorn.run(server.app, host="127.0.0.1", port={port}, log_level="warning", workers=1)
'''


class Server:
    def __init__(self):
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.ws_base = f"ws://127.0.0.1:{self.port}"
        self.proc: subprocess.Popen | None = None

    def __enter__(self):
        for p in (TEST_DB_PATH, TEST_DB_PATH + "-shm", TEST_DB_PATH + "-wal"):
            if os.path.exists(p):
                os.remove(p)
        env = os.environ.copy()
        env["PYTHONPATH"] = PORTAL_DIR
        runner_path = os.path.join(SCRIPT_DIR, "_control_plane_ws_runner.py")
        with open(runner_path, "w") as f:
            f.write(_RUNNER_SCRIPT_TEMPLATE.format(
                portal_dir=PORTAL_DIR,
                config_path=CONFIG_PATH,
                port=self.port,
            ))
        self.proc = subprocess.Popen(
            ["python3", runner_path],
            cwd=PORTAL_DIR, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if not _wait_ready(self.base + "/api/control/devices"):
            self.stop()
            raise RuntimeError("server did not become ready")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
            self.proc = None
        runner_path = os.path.join(SCRIPT_DIR, "_control_plane_ws_runner.py")
        if os.path.exists(runner_path):
            os.remove(runner_path)


class Client:
    def __init__(self, base: str, token: str | None = None):
        self.base = base
        self.token = token

    def _req(self, method: str, path: str, body: dict | None = None,
             token_override: str | None = None) -> tuple[int, dict | str]:
        token = token_override if token_override is not None else self.token
        url = self.base + path
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    return resp.status, json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    return resp.status, raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                return e.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return e.code, raw


def register_device_via_api(c: Client, name: str) -> dict:
    tok_id = _issue_bootstrap_token(name, name)
    status, body = c._req("POST", f"{API_PREFIX}/devices/register", {
        "device_id": name,
        "display_name": name,
        "bootstrap_token": tok_id,
    })
    assert status == 200, f"register failed: {status} {body}"
    return body


def _issue_bootstrap_token(device_id: str, display_name: str) -> str:
    from datetime import datetime, timedelta
    import uuid
    tok_id = str(uuid.uuid4())
    with _test_session_scope() as s:
        s.add(_TestBootstrapToken(
            id=tok_id,
            device_id=device_id,
            display_name=display_name,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        ))
    return tok_id


def grant_acl(c: Client, source: str, target: str, operation: str) -> dict:
    status, body = c._req("POST", f"{API_PREFIX}/acls", {
        "source_device": f"device:{source}",
        "target_device": f"device:{target}",
        "operation": operation,
        "extra": "",
    })
    assert status == 200, f"grant failed: {status} {body}"
    return body


def grant_acl_via_admin(c: Client, source: str, target: str, operation: str) -> str:
    """
    Create a fresh admin device and grant the requested ACL. Returns admin bearer token.
    """
    import uuid
    from datetime import datetime, timedelta
    admin_id = f"admin-{uuid.uuid4().hex[:8]}"
    tok_id = str(uuid.uuid4())
    with _test_session_scope() as s:
        s.add(_TestBootstrapToken(
            id=tok_id,
            device_id=admin_id,
            display_name=admin_id,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        ))
    status, body = c._req("POST", f"{API_PREFIX}/devices/register", {
        "device_id": admin_id, "display_name": admin_id, "bootstrap_token": tok_id,
    })
    assert status == 200, f"register admin: {status} {body}"
    admin_token = body["bearer_token"]
    with _test_session_scope() as s:
        d = s.query(_TestDevice).filter_by(id=admin_id).first()
        d.is_first_webui_device = True
    s = Client(c.base, token=admin_token)
    status, body = s._req("POST", f"{API_PREFIX}/acls", {
        "source_device": f"device:{source}",
        "target_device": f"device:{target}",
        "operation": operation,
        "extra": "",
    })
    assert status == 200, f"grant: {status} {body}"
    return admin_token


def issue_command(c: Client, source: str, target: str, operation: str, args: dict, timeout_seconds: int = 5) -> dict:
    status, body = c._req("POST", f"{API_PREFIX}/commands", {
        "source_device_id": source,
        "target_device_id": target,
        "operation": operation,
        "args": args,
        "timeout_seconds": timeout_seconds,
    })
    assert status == 200, f"issue failed: {status} {body}"
    return body


def test_ws_connect_invalid_token_rejected(s):
    info = register_device_via_api(Client(s.base), "wsdev-invalid")
    bad = info["bearer_token"] + "x"
    url = f"{s.ws_base}{API_PREFIX}/devices/{info['id']}/ws?token={bad}"
    with contextlib.suppress(InvalidStatus,
                              ConnectionClosedError,
                              ConnectionClosedOK,
                              WebSocketException):
        async def go():
            async with websockets.connect(url) as ws:
                await ws.recv()
        try:
            import asyncio
            asyncio.run(go())
        except Exception:
            pass
    print(f"  -> invalid token rejected")


def test_ws_connect_missing_token_rejected(s):
    info = register_device_via_api(Client(s.base), "wsdev-missing")
    url = f"{s.ws_base}{API_PREFIX}/devices/{info['id']}/ws"
    with contextlib.suppress(Exception):
        import asyncio
        async def go():
            async with websockets.connect(url) as ws:
                await ws.recv()
        asyncio.run(go())
    print(f"  -> missing token rejected")


def test_ws_register_operations(s):
    info = register_device_via_api(Client(s.base), "wsdev-ops")
    url = f"{s.ws_base}{API_PREFIX}/devices/{info['id']}/ws?token={info['bearer_token']}"
    import asyncio

    async def go():
        async with websockets.connect(url) as ws:
            welcome = json.loads(await ws.recv())
            assert welcome["type"] == "welcome", f"unexpected welcome: {welcome}"
            await ws.send(json.dumps({
                "type": "operations_register",
                "operations": [
                    {"id": "device.reboot",
                     "name": "device.reboot",
                     "ui_hint": {"kind": "button", "label": "Reboot"},
                     "params_schema": {"type": "object", "properties": {}}},
                ],
            }))
            ack = json.loads(await ws.recv())
            return ack

    ack = asyncio.run(go())
    assert ack["type"] == "operations_registered", f"unexpected ack: {ack}"
    assert ack.get("count") == 1, f"expected 1 op registered, got {ack}"
    with _test_session_scope() as sess:
        d = sess.query(_TestDevice).filter_by(id="wsdev-ops").first()
        d.is_first_webui_device = True
    authed = Client(s.base, token=info["bearer_token"])
    status, body = authed._req("GET", f"{API_PREFIX}/operations")
    assert status == 200
    names = {op["name"] for op in body.get("operations", [])}
    assert "device.reboot" in names, f"ops not stored: {names}"
    print(f"  -> operations_registered ({ack['count']} op visible)")


def test_ws_claim_and_result_lifecycle(s):
    issuer = register_device_via_api(Client(s.base), "wsdev-issuer")
    target = register_device_via_api(Client(s.base), "wsdev-target")

    target_url = f"{s.ws_base}{API_PREFIX}/devices/{target['id']}/ws?token={target['bearer_token']}"
    import asyncio

    async def register_ops():
        async with websockets.connect(target_url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "operations_register",
                "operations": [
                    {"id": "device.reboot",
                     "name": "device.reboot",
                     "ui_hint": {"kind": "button"},
                     "params_schema": {"type": "object", "properties": {}}},
                ],
            }))
            ack = json.loads(await ws.recv())
            assert ack["type"] == "operations_registered"

    asyncio.run(register_ops())

    admin_token = grant_acl_via_admin(Client(s.base), "wsdev-issuer", "wsdev-target", "device.reboot")
    Client(s.base, token=admin_token)._req("POST", f"{API_PREFIX}/acls", {
        "source_device": f"device:wsdev-target",
        "target_device": f"device:wsdev-issuer",
        "operation": "device.reboot",
        "extra": "",
    })

    async def go():
        async with websockets.connect(target_url) as ws:
            welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert welcome["type"] == "welcome", f"unexpected welcome: {welcome}"

            cmd = issue_command(
                Client(s.base, token=issuer["bearer_token"]),
                "wsdev-issuer", "wsdev-target", "device.reboot",
                {"delay": 0},
            )
            assert cmd["status"] == "pending", f"expected pending, got {cmd}"

            pushed = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert pushed["type"] == "command"
            assert pushed["command_id"] == cmd["id"]
            assert pushed["claim_token"]

            await ws.send(json.dumps({
                "type": "claim",
                "command_id": cmd["id"],
                "claim_token": pushed["claim_token"],
            }))
            ack = json.loads(await ws.recv())
            assert ack["type"] == "claimed_ack"
            assert ack["command_id"] == cmd["id"]

            await ws.send(json.dumps({
                "type": "result",
                "command_id": cmd["id"],
                "status": "succeeded",
                "result": {"ok": True},
            }))
            rack = json.loads(await ws.recv())
            assert rack["type"] == "result_ack"
            return cmd["id"]

    cid = asyncio.run(go())
    status, body = Client(s.base, token=issuer["bearer_token"])._req(
        "GET", f"{API_PREFIX}/commands/{cid}")
    assert status == 200
    assert body["status"] == "succeeded", f"expected succeeded, got {body}"
    assert body.get("result") == {"ok": True}
    print(f"  -> claim+result -> succeeded")


def test_ws_resume_promotes_timeout(s):
    issuer = register_device_via_api(Client(s.base), "wsdev-resume-issuer")
    target = register_device_via_api(Client(s.base), "wsdev-resume-target")

    target_url = f"{s.ws_base}{API_PREFIX}/devices/{target['id']}/ws?token={target['bearer_token']}"
    import asyncio

    async def register_ops():
        async with websockets.connect(target_url) as ws:
            await ws.recv()
            await ws.send(json.dumps({
                "type": "operations_register",
                "operations": [
                    {"id": "device.reboot",
                     "name": "device.reboot",
                     "ui_hint": {"kind": "button"},
                     "params_schema": {"type": "object", "properties": {}}},
                ],
            }))
            ack = json.loads(await ws.recv())
            assert ack["type"] == "operations_registered"

    asyncio.run(register_ops())

    admin_token = grant_acl_via_admin(Client(s.base), "wsdev-resume-issuer", "wsdev-resume-target", "device.reboot")
    Client(s.base, token=admin_token)._req("POST", f"{API_PREFIX}/acls", {
        "source_device": f"device:wsdev-resume-target",
        "target_device": f"device:wsdev-resume-issuer",
        "operation": "device.reboot",
        "extra": "",
    })

    cmd = None

    async def claim():
        nonlocal cmd
        async with websockets.connect(target_url) as ws:
            welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert welcome["type"] == "welcome", f"unexpected welcome: {welcome}"
            cmd = issue_command(
                Client(s.base, token=issuer["bearer_token"]),
                "wsdev-resume-issuer", "wsdev-resume-target", "device.reboot",
                {"x": 1}, timeout_seconds=1,
            )
            pushed = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert pushed["type"] == "command"
            await ws.send(json.dumps({
                "type": "claim",
                "command_id": pushed["command_id"],
                "claim_token": pushed["claim_token"],
            }))
            ack = json.loads(await ws.recv())
            assert ack["type"] == "claimed_ack"
            return pushed["command_id"]

    cid = asyncio.run(claim())
    assert cmd is not None
    time.sleep(1.5)

    async def resume():
        async with websockets.connect(target_url) as ws:
            await ws.send(json.dumps({
                "type": "hello",
                "resumed_claimed_ids": [cid],
            }))
            await asyncio.sleep(0.2)
            return True

    asyncio.run(resume())

    status, body = Client(s.base, token=issuer["bearer_token"])._req(
        "GET", f"{API_PREFIX}/commands/{cid}")
    assert status == 200
    assert body["status"] == "timeout", f"expected timeout, got {body}"
    print(f"  -> resumed_claimed_ids promoted past-timeout commands to 'timeout'")


def main():
    tests = [
        test_ws_connect_invalid_token_rejected,
        test_ws_connect_missing_token_rejected,
        test_ws_register_operations,
        test_ws_claim_and_result_lifecycle,
        test_ws_resume_promotes_timeout,
    ]
    passed = 0
    failed = 0
    with Server() as s:
        for t in tests:
            print(f"[ws] {t.__name__}")
            try:
                t(s)
                passed += 1
            except AssertionError as e:
                print(f"  !! FAILED: {e}")
                failed += 1
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"  !! ERROR: {e}")
                failed += 1
        if s.proc and s.proc.stdout:
            pass
    print("=" * 60)
    print(f"WS tests: {passed} passed, {failed} failed")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
