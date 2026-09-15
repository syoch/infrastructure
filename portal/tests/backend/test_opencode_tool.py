#!/usr/bin/env python3
"""Tests for the OpenCode helper CLI (portal-opencode-tool) and OpenCodeOps."""
import io
import json
import os
import sys
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

from servers.app_portal.opencode_ops import OpenCodeOps, server_key_for
from servers.app_portal.opencode_tool import main as tool_main


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


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _run_tool(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = tool_main(argv)
    return code, buf.getvalue().strip()


def run_all():
    print("=" * 60)
    print("      OpenCode helper CLI tests")
    print("=" * 60)

    server = HTTPServer(("127.0.0.1", 0), _FakeOpenCode)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    webui = "http://127.0.0.1:12000"
    expected_key = server_key_for(webui)

    try:
        ops = OpenCodeOps(base, webui)

        print("\n[ops] webui_url construction")
        url = ops.webui_url("ses_a")
        _assert(url == f"{webui}/server/{expected_key}/session/ses_a", f"unexpected: {url}")
        print(f"  -> {url}")

        print("\n[ops] list_sessions (all)")
        result = ops.list_sessions()
        _assert(len(result["sessions"]) == 2, f"unexpected: {result}")
        print("  -> 2 sessions")

        print("\n[ops] list_sessions (filtered)")
        result = ops.list_sessions("/home/syoch/work/iwara-rev")
        _assert(len(result["sessions"]) == 1 and result["sessions"][0]["id"] == "ses_a", result)
        print("  -> 1 session (ses_a)")

        print("\n[ops] inject_feedback")
        result = ops.inject_feedback("ses_a", "hello from app portal")
        _assert(result["webui_url"].endswith("/session/ses_a"), result)
        _assert(len(_FakeOpenCode.prompts) == 1, _FakeOpenCode.prompts)
        path, body = _FakeOpenCode.prompts[0]
        _assert("/session/ses_a/prompt_async" in path, path)
        _assert(body["parts"][0]["text"] == "hello from app portal", body)
        print("  -> injected")

        print("\n[ops] traits payload")
        traits = ops.traits()
        _assert(traits["operations"]["feedback"] == "opencode.feedback", traits)
        _assert(traits["webui_base_url"] == webui and traits["server_key"] == expected_key, traits)
        _assert("opencode.list_sessions" in traits["keys"], traits)
        print("  -> OK")

        print("\n[cli] traits")
        code, out = _run_tool(["--opencode-url", base, "--webui-base-url", webui, "traits"])
        _assert(code == 0, f"exit {code}")
        payload = json.loads(out)
        _assert(payload["operations"]["feedback"] == "opencode.feedback", payload)
        _assert(payload["server_key"] == expected_key, payload)
        print("  -> OK")

        print("\n[cli] feedback")
        code, out = _run_tool([
            "--opencode-url", base, "--webui-base-url", webui, "feedback",
            "--session-id", "ses_a", "--prompt", "cli feedback",
        ])
        _assert(code == 0, f"exit {code}")
        payload = json.loads(out)
        _assert(payload["session_id"] == "ses_a", payload)
        _assert(payload["webui_url"].endswith("/session/ses_a"), payload)
        print("  -> OK")

        print("\n[cli] webui-url")
        code, out = _run_tool(["--opencode-url", base, "--webui-base-url", webui, "webui-url"])
        payload = json.loads(out)
        _assert(payload["server_key"] == expected_key, payload)
        print("  -> OK")

        print("\n[cli] unreachable opencode -> exit 1")
        code, _ = _run_tool(["--opencode-url", "http://127.0.0.1:1", "list-sessions"])
        _assert(code == 1, f"expected exit 1, got {code}")
        print("  -> exit 1 as expected")
    finally:
        server.shutdown()

    print("\n" + "=" * 60)
    print("      ALL OPENCODE HELPER TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
