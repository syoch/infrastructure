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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(SCRIPT_DIR)
PORTAL_DIR = os.path.dirname(TESTS_DIR)
ROOT_DIR = os.path.dirname(PORTAL_DIR)

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

CONFIG_PATH = os.path.join(PORTAL_DIR, "tests", "config.test.json")
TEST_DB_PATH = os.path.join(PORTAL_DIR, "tests", "portal_test.db")

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


class Server:
    def __init__(self):
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc: subprocess.Popen | None = None

    def __enter__(self):
        for p in (TEST_DB_PATH, TEST_DB_PATH + "-shm", TEST_DB_PATH + "-wal"):
            if os.path.exists(p):
                os.remove(p)
        env = os.environ.copy()
        env["PYTHONPATH"] = PORTAL_DIR
        runner_path = os.path.join(SCRIPT_DIR, "_control_plane_server_runner.py")
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
        runner_path = os.path.join(SCRIPT_DIR, "_control_plane_server_runner.py")
        if os.path.exists(runner_path):
            os.remove(runner_path)


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
uvicorn.run(server.app, host="127.0.0.1", port={port}, log_level="warning", workers=1)
'''


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
            resp = urllib.request.urlopen(req, timeout=5)
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.getcode(), json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.getcode(), raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                return e.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return e.code, raw
        except Exception as e:
            return 0, str(e)

    def get(self, path: str, **kw):
        return self._req("GET", path, **kw)

    def post(self, path: str, body: dict | None = None, **kw):
        return self._req("POST", path, body, **kw)

    def patch(self, path: str, body: dict | None = None, **kw):
        return self._req("PATCH", path, body, **kw)

    def delete(self, path: str, **kw):
        return self._req("DELETE", path, **kw)


def _assert(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def _seed_device(db_path: str, device_id: str, display_name: str,
                 token: str, is_admin: bool = False):
    sys.path.insert(0, PORTAL_DIR)
    from backend.core import config
    config.load_config_from_file(CONFIG_PATH)
    from backend.core.database import session_scope
    from servers.control_plane.models import Device
    with session_scope() as s:
        s.add(Device(
            id=device_id,
            display_name=display_name,
            bearer_token=token,
            is_first_webui_device=is_admin,
        ))


def _seed_acl(source: str, target: str, operation: str):
    from backend.core import config
    config.load_config_from_file(CONFIG_PATH)
    from backend.core.database import session_scope
    from servers.control_plane.models import DeviceACL
    with session_scope() as s:
        s.add(DeviceACL(
            source_device=source,
            target_device=target,
            operation=operation,
        ))


def _seed_operation(op_id: str, provider: str, group: str, name: str):
    from backend.core import config
    config.load_config_from_file(CONFIG_PATH)
    from backend.core.database import session_scope
    from servers.control_plane.models import OperationSpec
    with session_scope() as s:
        s.add(OperationSpec(
            id=op_id,
            provider=provider,
            group=group,
            name=name,
            params_schema={},
        ))


def _issue_bootstrap_token(device_id: str, display_name: str) -> str:
    from backend.core import config
    config.load_config_from_file(CONFIG_PATH)
    from backend.core.database import session_scope
    from servers.control_plane.models import DeviceBootstrapToken
    from datetime import datetime, timedelta
    import uuid
    tok_id = str(uuid.uuid4())
    with session_scope() as s:
        s.add(DeviceBootstrapToken(
            id=tok_id,
            device_id=device_id,
            display_name=display_name,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        ))
    return tok_id


def run_all():
    print("=" * 60)
    print("      Control Plane: Auth + REST API tests")
    print("=" * 60)

    with Server() as srv:
        base = srv.base

        c_noauth = Client(base)

        # ==== Auth ====
        print("\n[auth] missing Authorization header")
        code, body = c_noauth.get(API_PREFIX + "/devices")
        _assert(code == 401, f"expected 401, got {code}: {body}")
        print("  -> 401 OK")

        print("\n[auth] invalid token")
        code, body = c_noauth.get(API_PREFIX + "/devices", token_override="tk_invalid")
        _assert(code == 401, f"expected 401, got {code}: {body}")
        print("  -> 401 OK")

        # ==== first-webui-device auto promotion ====
        print("\n[promotion] seed 1 device, GET /me should promote to admin")
        _seed_device(TEST_DB_PATH, "laptop-1", "Laptop One", "tk_laptop1")
        c1 = Client(base, token="tk_laptop1")
        code, body = c1.get(API_PREFIX + "/devices/me")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        _assert(body.get("is_first_webui_device") is True, f"expected admin True, got {body}")
        _assert("bearer_token" in body and body["bearer_token"].startswith("tk_"),
                f"expected bearer_token in response, got {body}")
        print(f"  -> 200 OK, admin promoted, token: {body['bearer_token'][:12]}...")

        print("\n[promotion] second /me should NOT steal admin (last-writer-wins: no-op)")
        _seed_device(TEST_DB_PATH, "laptop-2", "Laptop Two", "tk_laptop2")
        c2 = Client(base, token="tk_laptop2")
        code, body = c2.get(API_PREFIX + "/devices/me")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        _assert(body.get("is_first_webui_device") is False, f"expected admin False, got {body}")
        print("  -> 200 OK, admin flag preserved on laptop-1")

        # ==== devices list ====
        print("\n[devices] list devices (admin can see all)")
        code, body = c1.get(API_PREFIX + "/devices")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        ids = [d["id"] for d in body["devices"]]
        _assert("laptop-1" in ids and "laptop-2" in ids, f"missing devices: {ids}")
        print(f"  -> 200 OK, devices: {ids}")

        # ==== rename: self OK ====
        print("\n[rename] self rename")
        code, body = c2.patch(API_PREFIX + "/devices/laptop-2", {"display_name": "Laptop Two Renamed"})
        _assert(code == 200, f"expected 200, got {code}: {body}")
        _assert(body["display_name"] == "Laptop Two Renamed", f"unexpected: {body}")
        print("  -> 200 OK")

        # ==== rename: other -> non-admin gets 403 ====
        print("\n[rename] non-admin tries to rename other device -> 403")
        code, body = c2.patch(API_PREFIX + "/devices/laptop-1", {"display_name": "Hack"})
        _assert(code == 403, f"expected 403, got {code}: {body}")
        print("  -> 403 OK")

        # ==== admin rename other ====
        print("\n[rename] admin renames other device")
        code, body = c1.patch(API_PREFIX + "/devices/laptop-2", {"display_name": "Laptop Two Final"})
        _assert(code == 200, f"expected 200, got {code}: {body}")
        print("  -> 200 OK")

        # ==== ACL: non-admin POST /acls -> 403 ====
        print("\n[acl] non-admin POST /acls -> 403")
        code, body = c2.post(API_PREFIX + "/acls", {
            "source_device": "device:.*",
            "target_device": "device:.*",
            "operation": ".*",
        })
        _assert(code == 403, f"expected 403, got {code}: {body}")
        print("  -> 403 OK")

        # ==== ACL: admin creates wildcard ====
        print("\n[acl] admin creates wildcard ACL")
        code, body = c1.post(API_PREFIX + "/acls", {
            "source_device": "device:.*",
            "target_device": "device:.*",
            "operation": ".*",
        })
        _assert(code == 200, f"expected 200, got {code}: {body}")
        acl_id = body["id"]
        _assert(body["source_device"] == "device:.*", f"unexpected: {body}")
        print(f"  -> 200 OK, acl_id={acl_id[:8]}")

        # ==== ACL: validation rejects bad type prefix ====
        print("\n[acl] admin POST /acls with missing type prefix -> 422")
        code, body = c1.post(API_PREFIX + "/acls", {
            "source_device": "syoch-laptop",
            "target_device": "device:.*",
            "operation": ".*",
        })
        _assert(code == 422, f"expected 422, got {code}: {body}")
        print("  -> 422 OK")

        # ==== ACL: duplicate -> 409 ====
        print("\n[acl] duplicate ACL -> 409")
        code, body = c1.post(API_PREFIX + "/acls", {
            "source_device": "device:.*",
            "target_device": "device:.*",
            "operation": ".*",
        })
        _assert(code == 409, f"expected 409, got {code}: {body}")
        print("  -> 409 OK")

        # ==== ACL: list ====
        print("\n[acl] list ACLs")
        code, body = c2.get(API_PREFIX + "/acls")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        _assert(len(body["acls"]) == 1, f"expected 1 ACL, got {len(body['acls'])}")
        print("  -> 200 OK")

        # ==== ACL: revoke ====
        print("\n[acl] admin revokes ACL")
        code, body = c1.delete(API_PREFIX + f"/acls/{acl_id}")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        print("  -> 200 OK")

        # ==== register: bootstrap token ====
        print("\n[register] issue bootstrap token via CLI helper, then POST /register")
        tok_id = _issue_bootstrap_token("new-device", "New Device")
        code, body = c_noauth.post(API_PREFIX + "/devices/register", {
            "device_id": "new-device",
            "display_name": "New Device",
            "bootstrap_token": tok_id,
        })
        _assert(code == 200, f"expected 200, got {code}: {body}")
        _assert("bearer_token" in body, f"expected bearer_token, got {body}")
        new_token = body["bearer_token"]
        print(f"  -> 200 OK, new token: {new_token[:12]}...")

        # ==== register: consumed token -> 410 ====
        print("\n[register] consumed token -> 410")
        code, body = c_noauth.post(API_PREFIX + "/devices/register", {
            "device_id": "new-device-2",
            "display_name": "New Device 2",
            "bootstrap_token": tok_id,
        })
        _assert(code == 410, f"expected 410, got {code}: {body}")
        print("  -> 410 OK")

        # ==== commands: ACL denied ====
        print("\n[command] no ACL -> 403")
        _seed_operation("device.reboot", "device:new-device", "device", "Reboot")
        c_new = Client(base, token=new_token)
        code, body = c_new.post(API_PREFIX + "/commands", {
            "target_device_id": "new-device",
            "operation": "device.reboot",
        })
        _assert(code == 403, f"expected 403, got {code}: {body}")
        print("  -> 403 OK")

        # ==== commands: ACL allowed ====
        print("\n[command] ACL allows -> 200, command in pending")
        _seed_acl("device:.*", "device:.*", ".*")
        code, body = c_new.post(API_PREFIX + "/commands", {
            "target_device_id": "new-device",
            "operation": "device.reboot",
            "params": {"delay": 0},
        })
        _assert(code == 200, f"expected 200, got {code}: {body}")
        _assert(body["status"] == "pending", f"expected pending, got {body['status']}")
        _assert(body["source_device_id"] == "new-device", f"unexpected: {body}")
        cmd_id = body["id"]
        print(f"  -> 200 OK, command_id={cmd_id[:8]}, status=pending")

        # ==== commands: unknown operation -> 404 ====
        print("\n[command] unknown operation -> 404")
        code, body = c_new.post(API_PREFIX + "/commands", {
            "target_device_id": "new-device",
            "operation": "device.no-such-op",
        })
        _assert(code == 404, f"expected 404, got {code}: {body}")
        print("  -> 404 OK")

        # ==== commands: get by id ====
        print("\n[command] GET /commands/{id}")
        code, body = c_new.get(API_PREFIX + f"/commands/{cmd_id}")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        _assert(body["id"] == cmd_id, f"unexpected: {body}")
        print("  -> 200 OK")

        # ==== commands: another device cannot view ====
        print("\n[command] other device cannot view -> 403")
        code, body = c2.get(API_PREFIX + f"/commands/{cmd_id}")
        _assert(code == 403, f"expected 403, got {code}: {body}")
        print("  -> 403 OK")

        # ==== operations: filter for non-admin ====
        print("\n[operations] non-admin sees only operations they can target")
        code, body = c2.get(API_PREFIX + "/operations")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        op_ids = [o["id"] for o in body["operations"]]
        _assert("device.reboot" in op_ids, f"missing device.reboot: {op_ids}")
        print(f"  -> 200 OK, visible ops: {op_ids}")

        # ==== operations: admin sees all ====
        print("\n[operations] admin sees all operations")
        code, body = c1.get(API_PREFIX + "/operations")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        op_ids = [o["id"] for o in body["operations"]]
        _assert("device.reboot" in op_ids, f"missing: {op_ids}")
        print(f"  -> 200 OK, all ops: {op_ids}")

        # ==== set-admin ====
        print("\n[admin] admin transfers admin to another device")
        code, body = c1.post(API_PREFIX + "/devices/laptop-2/set-admin")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        _assert(body["id"] == "laptop-2", f"unexpected: {body}")
        _assert(body["is_first_webui_device"] is True, f"unexpected: {body}")
        print("  -> 200 OK, admin moved to laptop-2")

        # ==== old admin now non-admin ====
        print("\n[admin] old admin loses admin flag")
        code, body = c1.get(API_PREFIX + "/devices/me")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        _assert(body.get("is_first_webui_device") is False, f"unexpected: {body}")
        print("  -> 200 OK, is_first_webui_device=False")

        # ==== non-admin cannot set admin ====
        print("\n[admin] non-admin set-admin -> 403")
        code, body = c1.post(API_PREFIX + "/devices/new-device/set-admin")
        _assert(code == 403, f"expected 403, got {code}: {body}")
        print("  -> 403 OK")

        # ==== delete-device: admin can delete non-admin ====
        print("\n[delete] new admin (laptop-2) deletes laptop-1")
        c1_get_me = c1.get(API_PREFIX + "/devices/me")
        code, body = c2.delete(API_PREFIX + "/devices/laptop-1")
        _assert(code == 200, f"expected 200, got {code}: {body}")
        print("  -> 200 OK")

    print("\n" + "=" * 60)
    print("      ALL CONTROL PLANE TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
