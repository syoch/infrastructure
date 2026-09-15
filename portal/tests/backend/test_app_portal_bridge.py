#!/usr/bin/env python3
"""Unit tests for the App Portal OpenCode bridge (no real OpenCode required)."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

from servers.app_portal.bridge import OpenCodeOps, _execute_operation, server_key_for


class _FakeOpenCode(BaseHTTPRequestHandler):
    sessions = [
        {"id": "ses_a", "title": "A", "directory": "/home/syoch/work/iwara-rev", "projectID": "p1", "agent": "build"},
        {"id": "ses_b", "title": "B", "directory": "/home/syoch/other", "projectID": "p2", "agent": "plan"},
    ]
    prompts = []

    def log_message(self, *args):
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
            self._json(200, _FakeOpenCode.sessions)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        if self.path.endswith("/prompt_async"):
            _FakeOpenCode.prompts.append((self.path, json.loads(raw or b"{}")))
            self.send_response(204)
            self.end_headers()
        else:
            self._json(404, {"error": "not found"})


def _start_fake() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _FakeOpenCode)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def run_all():
    print("=" * 60)
    print("      App Portal bridge unit tests")
    print("=" * 60)

    server, base = _start_fake()
    try:
        webui = "http://127.0.0.1:12000"
        ops = OpenCodeOps(base, webui)
        expected_key = server_key_for(webui)

        print("\n[bridge] webui_url construction")
        url = ops.webui_url("ses_a")
        _assert(url == f"{webui}/server/{expected_key}/session/ses_a", f"unexpected: {url}")
        print(f"  -> {url}")

        print("\n[bridge] list_sessions (all)")
        result = _execute_operation(ops, "opencode.list_sessions", {})
        _assert(result["succeeded"], f"list failed: {result}")
        _assert(len(result["result"]["sessions"]) == 2, f"unexpected: {result}")
        print("  -> 2 sessions")

        print("\n[bridge] list_sessions (filtered by directory)")
        result = _execute_operation(ops, "opencode.list_sessions", {"directory": "/home/syoch/work/iwara-rev"})
        sessions = result["result"]["sessions"]
        _assert(len(sessions) == 1 and sessions[0]["id"] == "ses_a", f"unexpected: {result}")
        print("  -> 1 session (ses_a)")

        print("\n[bridge] inject_feedback")
        result = _execute_operation(ops, "opencode.feedback", {
            "session_id": "ses_a", "prompt": "hello from app portal",
        })
        _assert(result["succeeded"], f"inject failed: {result}")
        _assert(result["result"]["webui_url"].endswith("/session/ses_a"), f"unexpected: {result}")
        _assert(len(_FakeOpenCode.prompts) == 1, f"prompt not sent: {_FakeOpenCode.prompts}")
        path, body = _FakeOpenCode.prompts[0]
        _assert("/session/ses_a/prompt_async" in path, f"unexpected path: {path}")
        _assert(body["parts"][0]["text"] == "hello from app portal", f"unexpected body: {body}")
        print(f"  -> 204 accepted, webui_url={result['result']['webui_url']}")

        print("\n[bridge] inject_feedback missing params -> failed")
        result = _execute_operation(ops, "opencode.feedback", {"session_id": "ses_a"})
        _assert(not result["succeeded"], f"expected failure: {result}")
        print("  -> failed as expected")

        print("\n[bridge] webui_url operation")
        result = _execute_operation(ops, "opencode.webui_url", {})
        _assert(result["result"]["server_key"] == expected_key, f"unexpected: {result}")
        print("  -> OK")

        print("\n[bridge] unknown operation")
        result = _execute_operation(ops, "opencode.nope", {})
        _assert(not result["succeeded"], f"expected failure: {result}")
        print("  -> failed as expected")
    finally:
        server.shutdown()

    print("\n" + "=" * 60)
    print("      ALL APP PORTAL BRIDGE TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
