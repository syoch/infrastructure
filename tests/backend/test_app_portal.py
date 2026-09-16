#!/usr/bin/env python3
import base64
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(SCRIPT_DIR)
PORTAL_DIR = os.path.dirname(TESTS_DIR)
ROOT_DIR = os.path.dirname(PORTAL_DIR)

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

CONFIG_PATH = os.path.join(PORTAL_DIR, "tests", "config.test.json")
TEST_DB_PATH = os.path.join(PORTAL_DIR, "tests", "portal_test.db")

API = "/api/app-portal"
CTRL = "/api/control"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(url: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=1.0).read()
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            time.sleep(0.3)
    return False


_RUNNER_SCRIPT_TEMPLATE = '''
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


class Server:
    def __init__(self):
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc = None

    def __enter__(self):
        for p in (TEST_DB_PATH, TEST_DB_PATH + "-wal", TEST_DB_PATH + "-shm"):
            if os.path.exists(p):
                os.remove(p)
        env = os.environ.copy()
        env["PYTHONPATH"] = PORTAL_DIR
        runner_path = os.path.join(SCRIPT_DIR, "_app_portal_runner.py")
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
        if not _wait_ready(self.base + CTRL + "/devices"):
            self.stop()
            raise RuntimeError("server did not become ready")
        return self

    def __exit__(self, *_):
        self.stop()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        runner_path = os.path.join(SCRIPT_DIR, "_app_portal_runner.py")
        if os.path.exists(runner_path):
            os.remove(runner_path)


class Client:
    def __init__(self, base: str, token: str | None = None):
        self.base = base
        self.token = token

    def _req(self, method: str, path: str, body: dict | None = None):
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            raw = resp.read().decode()
            return resp.getcode(), json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                return e.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return e.code, raw

    def get(self, path, **kw):
        return self._req("GET", path, **kw)

    def post(self, path, body=None):
        return self._req("POST", path, body)

    def patch(self, path, body=None):
        return self._req("PATCH", path, body)

    def delete(self, path):
        return self._req("DELETE", path)


def _assert(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def _run_cli(args: list[str]) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = PORTAL_DIR
    proc = subprocess.run(
        ["python3", os.path.join(PORTAL_DIR, "backend", "manage.py"),
         "--config", CONFIG_PATH, "control", *args],
        cwd=PORTAL_DIR, env=env, capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"manage.py control {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout


def _run_app_portal_cli(args: list[str]) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = PORTAL_DIR
    proc = subprocess.run(
        ["python3", os.path.join(PORTAL_DIR, "backend", "manage.py"),
         "--config", CONFIG_PATH, "app-portal", *args],
        cwd=PORTAL_DIR, env=env, capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"manage.py app-portal {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout


def _issue_bootstrap_token(device_id: str, display_name: str) -> str:
    out = _run_cli(["issue-bootstrap-token", "--device-id", device_id, "--display-name", display_name])
    for line in out.splitlines():
        if line.startswith("Bootstrap token:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"bootstrap token not found in: {out}")


def _register(base: str, device_id: str, display_name: str, token: str) -> dict:
    c = Client(base)
    code, body = c.post(CTRL + "/devices/register", {
        "device_id": device_id, "display_name": display_name, "bootstrap_token": token,
    })
    _assert(code == 200, f"register {device_id} failed: {code} {body}")
    return body


def _set_feedback_command_result(command_id: str, webui_url: str, session_id: str):
    sys.path.insert(0, PORTAL_DIR)
    from backend.core import config
    config.load_config_from_file(CONFIG_PATH)
    from backend.core.database import session_scope
    from backend.control_plane.models import CommandRequest
    from datetime import datetime
    with session_scope() as s:
        cmd = s.query(CommandRequest).filter_by(id=command_id).first()
        _assert(cmd is not None, f"command {command_id} not found")
        cmd.status = "succeeded"
        cmd.completed_at = datetime.utcnow()
        cmd.result = {"webui_url": webui_url, "session_id": session_id}


def run_all():
    print("=" * 60)
    print("      App Portal: REST + feedback delivery tests")
    print("=" * 60)

    with Server() as server:
        base = server.base

        # --- devices ---
        admin_id = "app-admin"
        bridge_id = "opencode-bridge"
        admin_reg = _register(base, admin_id, "App Admin", _issue_bootstrap_token(admin_id, "App Admin"))
        bridge_reg = _register(base, bridge_id, "OpenCode Bridge", _issue_bootstrap_token(bridge_id, "OpenCode Bridge"))
        _run_cli(["set-admin", "--device-id", admin_id])

        admin = Client(base, admin_reg["bearer_token"])
        bridge = Client(base, bridge_reg["bearer_token"])

        # --- auth ---
        print("\n[auth] no token -> 401")
        code, _ = Client(base).get(API + "/apps")
        _assert(code == 401, f"expected 401, got {code}")
        print("  -> 401 OK")

        # --- bridge announce ---
        print("\n[bridge] announce webui base url")
        code, body = bridge.post(API + "/bridges/announce", {
            "webui_base_url": "http://127.0.0.1:12000",
            "hostname": "dev-host",
        })
        _assert(code == 200, f"announce failed: {code} {body}")
        expected_key = base64.urlsafe_b64encode(b"http://127.0.0.1:12000").decode().rstrip("=")
        _assert(body["server_key"] == expected_key, f"server_key mismatch: {body}")
        print(f"  -> 200 OK, server_key={body['server_key']}")

        # --- app registration (device auth) ---
        print("\n[app] create app via bridge token")
        code, app = bridge.post(API + "/apps", {
            "name": "Iwara Rev",
            "description": "Test app",
            "url": "http://127.0.0.1:5173",
            "project_directory": "/home/syoch/work/iwara-rev",
            "opencode_session_id": "ses_test_iwara",
            "source": "opencode",
            "tags": ["web"],
        })
        _assert(code == 200, f"create app failed: {code} {app}")
        slug = app["slug"]
        _assert(app["bridge_device_id"] == bridge_id, f"unexpected bridge: {app}")
        _assert(app["webui_url"].endswith("/server/%s/session/ses_test_iwara" % expected_key),
                f"unexpected webui_url: {app['webui_url']}")
        print(f"  -> 200 OK, slug={slug} webui_url={app['webui_url']}")

        print("\n[app] duplicate slug -> 409")
        code, _ = bridge.post(API + "/apps", {
            "name": "Iwara Rev", "project_directory": "/x", "opencode_session_id": "ses_x",
        })
        _assert(code == 409, f"expected 409, got {code}")
        print("  -> 409 OK")

        print("\n[app] list apps")
        code, body = bridge.get(API + "/apps")
        _assert(code == 200 and len(body["apps"]) == 1, f"list failed: {code} {body}")
        print("  -> 200 OK")

        # --- feedback submit (admin) ---
        print("\n[feedback] non-admin submit -> 403")
        code, _ = bridge.post(API + f"/apps/{slug}/feedback", {"body": "hi"})
        _assert(code == 403, f"expected 403, got {code}")
        print("  -> 403 OK")

        print("\n[feedback] admin submit -> pending command")
        code, fb = admin.post(API + f"/apps/{slug}/feedback", {
            "body": "動画一覧のソートが効かない", "kind": "bug",
        })
        _assert(code == 200, f"feedback failed: {code} {fb}")
        _assert(fb["status"] == "pending", f"expected pending: {fb}")
        _assert(fb["command_id"], f"missing command_id: {fb}")
        _assert(fb["target_session_id"] == "ses_test_iwara", f"unexpected target: {fb}")
        print(f"  -> 200 OK, command_id={fb['command_id'][:8]}")

        print("\n[feedback] app detail reconciles pending before delivery")
        code, detail = admin.get(API + f"/apps/{slug}")
        _assert(code == 200, f"detail failed: {code} {detail}")
        _assert(detail["feedback"][0]["status"] == "pending", f"unexpected: {detail['feedback'][0]}")
        print("  -> 200 OK (still pending)")

        # --- simulate bridge delivery ---
        print("\n[feedback] simulate bridge result -> delivered")
        _set_feedback_command_result(fb["command_id"], app["webui_url"], "ses_test_iwara")
        code, refreshed = admin.post(API + f"/feedback/{fb['id']}/refresh")
        _assert(code == 200, f"refresh failed: {code} {refreshed}")
        _assert(refreshed["status"] == "delivered", f"expected delivered: {refreshed}")
        _assert(refreshed["webui_url"] == app["webui_url"], f"unexpected webui_url: {refreshed}")
        print(f"  -> 200 OK, delivered webui_url={refreshed['webui_url']}")

        # --- update/delete (admin only) ---
        print("\n[app] bridge cannot patch -> 403")
        code, _ = bridge.patch(API + f"/apps/{slug}", {"status": "archived"})
        _assert(code == 403, f"expected 403, got {code}")
        print("  -> 403 OK")

        print("\n[app] admin patch -> 200")
        code, body = admin.patch(API + f"/apps/{slug}", {"status": "archived"})
        _assert(code == 200 and body["status"] == "archived", f"patch failed: {code} {body}")
        print("  -> 200 OK")

        print("\n[app] CLI update-app -> 200")
        _run_app_portal_cli([
            "update-app", "--slug", slug,
            "--status", "active",
            "--description", "updated via cli",
            "--tag", "cli",
            "--tag", "updated",
        ])
        code, body = admin.get(API + f"/apps/{slug}")
        _assert(code == 200, f"get after cli update failed: {code} {body}")
        _assert(body["status"] == "active", f"cli status not applied: {body}")
        _assert(body["description"] == "updated via cli", f"cli description not applied: {body}")
        _assert(body["tags"] == ["cli", "updated"], f"cli tags not applied: {body}")
        print("  -> 200 OK")

        print("\n[app] admin delete -> 200")
        code, body = admin.delete(API + f"/apps/{slug}")
        _assert(code == 200, f"delete failed: {code} {body}")
        code, _ = admin.get(API + f"/apps/{slug}")
        _assert(code == 404, f"expected 404 after delete, got {code}")
        print("  -> 200 OK, 404 after delete")

    print("\n" + "=" * 60)
    print("      ALL APP PORTAL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
