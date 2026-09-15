#!/usr/bin/env python3
"""Integration test: portal + generic device agent + OpenCode helper CLI.

Validates the unified design: a single `portal-device-agent` advertises the
opencode operations (and a `traits.opencode-bridge` operation) as config-defined
shell commands invoking `portal-opencode-tool`. The portal discovers the
feedback operation key via the trait and parses the helper's stdout JSON.
"""
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(SCRIPT_DIR)
PORTAL_DIR = os.path.dirname(TESTS_DIR)
if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

CONFIG_PATH = os.path.join(PORTAL_DIR, "tests", "config.test.json")
TEST_DB_PATH = os.path.join(PORTAL_DIR, "tests", "portal_test.db")
API = "/api/app-portal"
CTRL = "/api/control"
WEBUI_BASE = "http://127.0.0.1:12000"
DEVICE_ID = "opencode-bridge"


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
            time.sleep(0.2)
    return False


class _FakeOpenCode(BaseHTTPRequestHandler):
    prompts = []

    def log_message(self, *a):
        pass

    def _json(self, code, payload):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/session":
            self._json(200, [{"id": "ses_e2e", "title": "E2E", "directory": "/tmp/e2e-app"}])
        else:
            self._json(404, {})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        if self.path.endswith("/prompt_async"):
            _FakeOpenCode.prompts.append(json.loads(raw))
            self.send_response(204)
            self.end_headers()
        else:
            self._json(404, {})


_RUNNER = '''
import sys
import uvicorn
sys.path.insert(0, {portal_dir!r})
from backend.core import config
config.load_config_from_file({config_path!r})
from backend.core.server_base import PortalServer
from backend.core.extension_loader import load_extensions
from backend.core.database import init_db
server = PortalServer(host="127.0.0.1", port={port})
exts = load_extensions(config)
init_db()
for e in exts:
    e.setup()
    server.register_extension(e)
    if hasattr(e, "install_event_loop_capture"):
        e.install_event_loop_capture(server.app)
uvicorn.run(server.app, host="127.0.0.1", port={port}, log_level="warning", workers=1)
'''


def _req(base, method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
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


def _run_cli(args):
    env = os.environ.copy()
    env["PYTHONPATH"] = PORTAL_DIR
    proc = subprocess.run(
        ["python3", os.path.join(PORTAL_DIR, "manage.py"), "--config", CONFIG_PATH, "control", *args],
        cwd=PORTAL_DIR, env=env, capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cli failed: {proc.stderr}")
    return proc.stdout


def _issue(device_id, name):
    out = _run_cli(["issue-bootstrap-token", "--device-id", device_id, "--display-name", name])
    for line in out.splitlines():
        if line.startswith("Bootstrap token:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(out)


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _agent_config(base, token, creds_file):
    helper = ["python3", "-m", "servers.app_portal.opencode_tool"]
    return {
        "device_id": DEVICE_ID,
        "display_name": "OpenCode Bridge",
        "server_url": base,
        "bootstrap_token": token,
        "credentials_file": creds_file,
        "operations": [
            {
                "id": "opencode.feedback", "name": "Send Feedback", "group": "opencode",
                "command": helper + ["feedback", "--session-id", "{session_id}", "--prompt", "{prompt}"],
                "params_schema": {"type": "object", "properties": {"session_id": {"type": "string"}, "prompt": {"type": "string"}}},
            },
            {
                "id": "opencode.list_sessions", "name": "List Sessions", "group": "opencode",
                "command": helper + ["list-sessions", "--directory", "{directory}"],
                "params_schema": {"type": "object", "properties": {"directory": {"type": "string"}}},
            },
            {
                "id": "opencode.webui_url", "name": "WebUI URL", "group": "opencode",
                "command": helper + ["webui-url"],
                "params_schema": {"type": "object", "properties": {}},
            },
            {
                "id": "traits.opencode-bridge", "name": "Traits", "group": "opencode",
                "command": helper + ["traits"],
                "params_schema": {"type": "object", "properties": {}},
            },
            {
                "id": "sys.dpms_toggle", "name": "Toggle DPMS", "group": "system",
                "command": ["true"],
                "params_schema": {"type": "object", "properties": {}},
                "ui_hint": {"kind": "button", "label": "Toggle DPMS"},
            },
        ],
    }


def _wait_device_online(base, admin_token, device_id, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, body = _req(base, "GET", CTRL + "/devices", token=admin_token)
        if code == 200:
            for d in body.get("devices", []):
                if d["id"] == device_id and d.get("ws_state") == "online":
                    return True
        time.sleep(0.3)
    return False


def _wait_delivered(base, admin_token, slug, feedback_id, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, detail = _req(base, "GET", API + f"/apps/{slug}", token=admin_token)
        if code == 200:
            for item in detail.get("feedback", []):
                if item["id"] == feedback_id and item["status"] == "delivered":
                    return item
        time.sleep(0.3)
    return None


def run_all():
    print("=" * 60)
    print("      App Portal: device-agent delivery integration test")
    print("=" * 60)

    fake = HTTPServer(("127.0.0.1", 0), _FakeOpenCode)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    fake_url = f"http://127.0.0.1:{fake.server_port}"

    for p in (TEST_DB_PATH, TEST_DB_PATH + "-wal", TEST_DB_PATH + "-shm"):
        if os.path.exists(p):
            os.remove(p)

    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    runner = os.path.join(SCRIPT_DIR, "_app_portal_agent_runner.py")
    with open(runner, "w") as f:
        f.write(_RUNNER.format(portal_dir=PORTAL_DIR, config_path=CONFIG_PATH, port=port))

    env = os.environ.copy()
    env["PYTHONPATH"] = PORTAL_DIR
    env["OPENCODE_URL"] = fake_url
    env["OPENCODE_WEBUI_BASE_URL"] = WEBUI_BASE

    server = subprocess.Popen(["python3", runner], cwd=PORTAL_DIR, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    agent = None
    agent_log = open("/tmp/device_agent_e2e.log", "w")
    try:
        _assert(_wait_ready(base + CTRL + "/devices"), "portal did not start")

        admin_tok = _issue("e2e-admin", "E2E Admin")
        code, reg = _req(base, "POST", CTRL + "/devices/register",
                         {"device_id": "e2e-admin", "display_name": "E2E Admin", "bootstrap_token": admin_tok})
        _assert(code == 200, f"admin register failed: {code} {reg}")
        admin = reg["bearer_token"]
        _run_cli(["set-admin", "--device-id", "e2e-admin"])

        token = _issue(DEVICE_ID, "OpenCode Bridge")
        creds_file = "/tmp/opencode-bridge-agent-creds.json"
        cfg_path = "/tmp/opencode-bridge-agent.json"
        for p in (creds_file, creds_file + ".tmp"):
            if os.path.exists(p):
                os.remove(p)
        with open(cfg_path, "w") as f:
            json.dump(_agent_config(base, token, creds_file), f)

        agent = subprocess.Popen(
            ["python3", "-m", "agents.device_agent", "--config", cfg_path],
            cwd=PORTAL_DIR, env=env, stdout=agent_log, stderr=subprocess.STDOUT,
        )

        print("\n[agent] waiting for device online")
        _assert(_wait_device_online(base, admin, DEVICE_ID), "device agent did not come online")
        print("  -> online")

        code, app = _req(base, "POST", API + "/apps", {
            "name": "E2E Agent App",
            "project_directory": "/tmp/e2e-app",
            "opencode_session_id": "ses_e2e",
            "bridge_device_id": DEVICE_ID,
        }, token=admin)
        _assert(code == 200, f"create app failed: {code} {app}")
        slug = app["slug"]

        print("\n[trait] app detail warms the opencode-bridge trait")
        code, detail = _req(base, "GET", API + f"/apps/{slug}", token=admin)
        _assert(code == 200, f"detail failed: {code} {detail}")
        _assert((detail.get("webui_url") or "").endswith("/session/ses_e2e"),
                f"webui_url not resolved via trait: {detail.get('webui_url')}")
        print(f"  -> {detail['webui_url']}")

        print("\n[feedback] submit and wait for delivery via device agent")
        code, fb = _req(base, "POST", API + f"/apps/{slug}/feedback",
                        {"body": "agent delivery feedback", "kind": "bug"}, token=admin)
        _assert(code == 200, f"feedback failed: {code} {fb}")
        _assert(fb["status"] == "pending", f"expected pending: {fb}")

        delivered = _wait_delivered(base, admin, slug, fb["id"])
        _assert(delivered is not None, "feedback was not delivered")
        _assert(delivered["webui_url"].endswith("/session/ses_e2e"), f"unexpected: {delivered}")
        print(f"  -> delivered, webui_url={delivered['webui_url']}")

        _assert(len(_FakeOpenCode.prompts) == 1, f"prompt not injected: {_FakeOpenCode.prompts}")
        prompt_text = _FakeOpenCode.prompts[0]["parts"][0]["text"]
        _assert("agent delivery feedback" in prompt_text, f"unexpected prompt: {prompt_text}")
        print("  -> prompt injected into OpenCode session")

        print("\n[dpms] device advertises the extra system operation")
        code, dev = _req(base, "GET", CTRL + f"/operations", token=admin)
        ids = [o["id"] for o in dev.get("operations", [])] if code == 200 else []
        _assert("sys.dpms_toggle" in ids, f"dpms operation missing: {ids}")
        print("  -> sys.dpms_toggle advertised")
    finally:
        if agent and agent.poll() is None:
            agent.send_signal(signal.SIGTERM)
            try:
                agent.wait(timeout=5)
            except subprocess.TimeoutExpired:
                agent.kill()
        if server.poll() is None:
            server.send_signal(signal.SIGTERM)
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        fake.shutdown()
        if os.path.exists(runner):
            os.remove(runner)

    print("\n" + "=" * 60)
    print("      ALL DEVICE-AGENT DELIVERY TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
