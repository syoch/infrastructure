#!/usr/bin/env python3
"""
Tests for the portal device agent.

Covers:
- Command template interpolation (string / list / shell modes)
- JSON Schema parameter validation
- Subprocess execution (success, non-zero exit, timeout)
- Agent class built-in operations (list/add/update/delete/test)
- Config load / save / reload round-trip
- End-to-end flow with a real portal server (register via bootstrap, claim, execute, return result)
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(SCRIPT_DIR)
PORTAL_DIR = os.path.dirname(TESTS_DIR)
ROOT_DIR = os.path.dirname(PORTAL_DIR)

CONFIG_PATH = os.path.join(PORTAL_DIR, "tests", "config.test.json")
TEST_DB_PATH = os.path.join(PORTAL_DIR, "tests", "portal_test.db")

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

from agents.device_agent import (
    Agent,
    _build_command,
    _execute_shell,
    _interpolate,
    _load_credentials,
    _materialize_operation,
    _op_dict,
    _parse_json_field,
    _save_credentials,
    _validate_params,
    load_config,
)
from agents.builtin_ops import BUILTIN_OPS, get_builtin_ops, is_builtin

from backend.core import config as _test_config
_test_config.load_config_from_file(CONFIG_PATH)
from backend.core.database import session_scope as _test_session_scope
from servers.control_plane.models import DeviceBootstrapToken as _TestBootstrapToken, Device as _TestDevice

import websockets


# ---------------------------------------------------------------------------
# Unit tests: command interpolation
# ---------------------------------------------------------------------------

def test_interpolate_simple(tmp_dir):
    assert _interpolate("hello {name}", {"name": "world"}) == "hello world"
    assert _interpolate("a-{x}-b-{y}", {"x": "1", "y": "2"}) == "a-1-b-2"
    assert _interpolate("no placeholders", {}) == "no placeholders"
    print("  -> interpolate simple: OK")


def test_interpolate_quoted(tmp_dir):
    s = _interpolate("echo {msg}", {"msg": "hello world"}, quote=True)
    assert s == "echo 'hello world'", s
    s2 = _interpolate("echo {x}", {"x": "it's"}, quote=True)
    assert s2 == "echo 'it'\"'\"'s'", s2
    print("  -> interpolate with shlex.quote: OK")


def test_interpolate_missing_param(tmp_dir):
    try:
        _interpolate("echo {x}", {})
    except RuntimeError as e:
        assert "missing param" in str(e), e
        print("  -> interpolate missing param raises: OK")
        return
    raise AssertionError("expected RuntimeError for missing param")


def test_build_command_list(tmp_dir):
    argv, shell = _build_command(["echo", "hello"], {}, use_shell=False)
    assert argv == ["echo", "hello"]
    assert shell is False
    print("  -> build_command list: OK")


def test_build_command_list_with_substitution(tmp_dir):
    argv, shell = _build_command(["echo", "{msg}"], {"msg": "hi"}, use_shell=False)
    assert argv == ["echo", "hi"]
    assert shell is False
    print("  -> build_command list with substitution: OK")


def test_build_command_string_shlex(tmp_dir):
    argv, shell = _build_command("echo {msg}", {"msg": "hi there"}, use_shell=False)
    assert argv == ["echo", "hi there"]
    assert shell is False
    print("  -> build_command string (shlex): OK")


def test_build_command_string_shell(tmp_dir):
    argv, shell = _build_command("echo {msg}", {"msg": "hi"}, use_shell=True)
    assert argv[:2] == ["sh", "-c"]
    assert shell is True
    assert "echo hi" in argv[2]
    print("  -> build_command shell mode: OK")


def test_build_command_list_shell_quoting(tmp_dir):
    argv, shell = _build_command(["rm", "-f", "{path}"], {"path": "my file.txt"}, use_shell=True)
    assert shell is True
    assert argv[2].endswith("'my file.txt'"), argv[2]
    print("  -> build_command list shell quoting: OK")


# ---------------------------------------------------------------------------
# Unit tests: param validation
# ---------------------------------------------------------------------------

def test_validate_params_ok(tmp_dir):
    schema = {
        "type": "object",
        "required": ["service"],
        "properties": {
            "service": {"type": "string"},
            "delay": {"type": "integer", "minimum": 0},
        },
    }
    _validate_params(schema, {"service": "nginx", "delay": 5})
    print("  -> validate_params ok: OK")


def test_validate_params_multiple_errors(tmp_dir):
    schema = {
        "type": "object",
        "required": ["service"],
        "properties": {
            "service": {"type": "string"},
            "delay": {"type": "integer", "minimum": 0},
        },
    }
    try:
        _validate_params(schema, {"delay": -1})
    except RuntimeError as e:
        msg = str(e)
        assert "service" in msg
        assert "delay" in msg
        print("  -> validate_params multiple errors aggregated: OK")
        return
    raise AssertionError("expected RuntimeError")


# ---------------------------------------------------------------------------
# Unit tests: subprocess execution
# ---------------------------------------------------------------------------

def test_execute_shell_success(tmp_dir):
    body = _execute_shell(["sh", "-c", "echo hello"], shell=False, timeout=5)
    assert body["succeeded"] is True
    assert body["result"]["exit_code"] == 0
    assert body["result"]["stdout"].strip() == "hello"
    print("  -> execute_shell success: OK")


def test_execute_shell_failure(tmp_dir):
    body = _execute_shell(["sh", "-c", "echo oops; exit 7"], shell=False, timeout=5)
    assert body["succeeded"] is False
    assert body["result"]["exit_code"] == 7
    assert "oops" in body["result"]["stdout"]
    print("  -> execute_shell non-zero exit: OK")


def test_execute_shell_timeout(tmp_dir):
    body = _execute_shell(["sh", "-c", "sleep 5"], shell=False, timeout=1)
    assert body["succeeded"] is False
    assert "timed out" in body["error"], body
    print("  -> execute_shell timeout: OK")


# ---------------------------------------------------------------------------
# Unit tests: config load / save
# ---------------------------------------------------------------------------

def _write_tmp_config(path: str, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f)


def test_load_config_minimal(tmp_dir):
    p = os.path.join(tmp_dir, "config.json")
    _write_tmp_config(p, {
        "device_id": "d1",
        "display_name": "D1",
        "server_url": "http://localhost:8000",
        "bootstrap_token": "bt",
    })
    cfg = load_config(p)
    assert cfg["device_id"] == "d1"
    assert cfg["operations"] == []
    print("  -> load_config minimal: OK")


def test_load_config_invalid(tmp_dir):
    p = os.path.join(tmp_dir, "bad.json")
    _write_tmp_config(p, {"device_id": 123, "operations": "not-a-list"})
    try:
        load_config(p)
    except Exception as e:
        print(f"  -> load_config rejects invalid: OK ({type(e).__name__})")
        return
    raise AssertionError("expected jsonschema error")


def test_credentials_roundtrip(tmp_dir):
    p = os.path.join(tmp_dir, "creds.json")
    _save_credentials(p, {"device_id": "d1", "bearer_token": "tk_x"})
    loaded = _load_credentials(p)
    assert loaded["bearer_token"] == "tk_x"
    print("  -> credentials save/load roundtrip: OK")


def test_parse_json_field_variants(tmp_dir):
    assert _parse_json_field('{"a": 1}', "x") == {"a": 1}
    assert _parse_json_field('null', "x") is None
    assert _parse_json_field("", "x") is None
    assert _parse_json_field({"a": 1}, "x") == {"a": 1}
    try:
        _parse_json_field("not json", "x")
    except RuntimeError:
        print("  -> parse_json_field rejects invalid: OK")
        return
    raise AssertionError("expected RuntimeError")


# ---------------------------------------------------------------------------
# Unit tests: Agent built-in operations
# ---------------------------------------------------------------------------

def _make_agent(tmp_dir: str) -> Agent:
    p = os.path.join(tmp_dir, "config.json")
    cfg = {
        "device_id": "agent-test",
        "display_name": "Agent Test",
        "server_url": "http://localhost:8000",
        "bootstrap_token": "bt_test",
        "operations": [],
    }
    _write_tmp_config(p, cfg)
    return Agent(p)


def test_agent_list_operations_empty(tmp_dir):
    a = _make_agent(tmp_dir)
    body = a._handle_builtin("device.config.list_operations", {})
    assert body["succeeded"]
    assert body["result"]["operations"] == []
    print("  -> agent list_operations empty: OK")


def test_agent_add_then_list(tmp_dir):
    a = _make_agent(tmp_dir)
    params = {
        "id": "system.reboot",
        "name": "Reboot",
        "command": ["systemctl", "reboot"],
        "shell": False,
        "timeout_seconds": 10,
        "params_schema": '{"type": "object", "properties": {}}',
    }
    body = a._handle_builtin("device.config.add_operation", params)
    assert body["succeeded"], body
    assert body["result"]["added"] == "system.reboot"
    body2 = a._handle_builtin("device.config.list_operations", {})
    assert len(body2["result"]["operations"]) == 1
    op = body2["result"]["operations"][0]
    assert op["id"] == "system.reboot"
    assert op["command"] == ["systemctl", "reboot"]
    print("  -> agent add + list roundtrip: OK")


def test_agent_add_duplicate_fails(tmp_dir):
    a = _make_agent(tmp_dir)
    params = {
        "id": "op.x", "name": "X", "command": ["true"],
        "params_schema": '{"type": "object", "properties": {}}',
    }
    a._handle_builtin("device.config.add_operation", params)
    body = a._handle_builtin("device.config.add_operation", params)
    assert not body["succeeded"]
    assert "already exists" in body["error"]
    print("  -> agent add duplicate rejected: OK")


def test_agent_cannot_modify_builtin(tmp_dir):
    a = _make_agent(tmp_dir)
    body = a._handle_builtin("device.config.add_operation", {
        "id": "device.config.list_operations",
        "name": "steal",
        "command": ["true"],
        "params_schema": '{"type": "object", "properties": {}}',
    })
    assert not body["succeeded"]
    assert "built-in" in body["error"]
    print("  -> agent cannot modify built-in: OK")


def test_agent_update_operation(tmp_dir):
    a = _make_agent(tmp_dir)
    a._handle_builtin("device.config.add_operation", {
        "id": "op.x", "name": "X", "command": ["true"],
        "params_schema": '{"type": "object", "properties": {}}',
    })
    body = a._handle_builtin("device.config.update_operation", {
        "id": "op.x", "name": "X updated", "command": ["false"],
        "params_schema": '{"type": "object", "properties": {}}',
    })
    assert body["succeeded"]
    body2 = a._handle_builtin("device.config.list_operations", {})
    op = body2["result"]["operations"][0]
    assert op["name"] == "X updated"
    assert op["command"] == ["false"]
    print("  -> agent update_operation: OK")


def test_agent_delete_operation(tmp_dir):
    a = _make_agent(tmp_dir)
    a._handle_builtin("device.config.add_operation", {
        "id": "op.x", "name": "X", "command": ["true"],
        "params_schema": '{"type": "object", "properties": {}}',
    })
    body = a._handle_builtin("device.config.delete_operation", {"id": "op.x"})
    assert body["succeeded"]
    body2 = a._handle_builtin("device.config.list_operations", {})
    assert body2["result"]["operations"] == []
    print("  -> agent delete_operation: OK")


def test_agent_test_operation(tmp_dir):
    a = _make_agent(tmp_dir)
    a._handle_builtin("device.config.add_operation", {
        "id": "echo.hello", "name": "Echo", "command": ["echo", "hi"],
        "params_schema": '{"type": "object", "properties": {}}',
    })
    body = a._handle_builtin("device.config.test_operation", {"id": "echo.hello"})
    assert body["succeeded"]
    assert body["result"]["exit_code"] == 0
    assert "hi" in body["result"]["stdout"]
    print("  -> agent test_operation: OK")


def test_agent_test_operation_with_params(tmp_dir):
    a = _make_agent(tmp_dir)
    a._handle_builtin("device.config.add_operation", {
        "id": "echo.msg", "name": "Echo Msg",
        "command": ["echo", "{msg}"],
        "params_schema": '{"type": "object", "properties": {"msg": {"type": "string"}}}',
    })
    body = a._handle_builtin("device.config.test_operation", {
        "id": "echo.msg",
        "params": '{"msg": "hello"}',
    })
    assert body["succeeded"], body
    assert "hello" in body["result"]["stdout"]
    print("  -> agent test_operation with params: OK")


def test_agent_test_validation_fails(tmp_dir):
    a = _make_agent(tmp_dir)
    a._handle_builtin("device.config.add_operation", {
        "id": "echo.required", "name": "Echo",
        "command": ["echo", "{msg}"],
        "params_schema": '{"type": "object", "required": ["msg"], "properties": {"msg": {"type": "string"}}}',
    })
    body = a._handle_builtin("device.config.test_operation", {
        "id": "echo.required",
        "params": "{}",
    })
    assert not body["succeeded"]
    assert "validation" in body["error"], body
    print("  -> agent test_operation validates params: OK")


def test_agent_get_config(tmp_dir):
    a = _make_agent(tmp_dir)
    body = a._handle_builtin("device.config.get_config", {})
    assert body["succeeded"]
    assert "config" in body["result"]
    parsed = json.loads(body["result"]["config"])
    assert parsed["device_id"] == "agent-test"
    print("  -> agent get_config returns raw JSON: OK")


def test_agent_reload_triggers_event(tmp_dir):
    a = _make_agent(tmp_dir)
    a.request_reload()
    assert a._reload_event.is_set()
    print("  -> agent reload sets event: OK")


def test_agent_reload_picks_up_changes(tmp_dir):
    a = _make_agent(tmp_dir)
    a._handle_builtin("device.config.add_operation", {
        "id": "op.original", "name": "Original", "command": ["true"],
        "params_schema": '{"type": "object", "properties": {}}',
    })
    with open(a.config_path, "w") as f:
        json.dump({
            "device_id": "agent-test",
            "display_name": "Agent Test",
            "server_url": "http://localhost:8000",
            "bootstrap_token": "bt_test",
            "operations": [
                {"id": "op.reloaded", "name": "Reloaded", "command": ["echo", "x"]},
            ],
        }, f)
    a.reload_config()
    body = a._handle_builtin("device.config.list_operations", {})
    ids = [op["id"] for op in body["result"]["operations"]]
    assert ids == ["op.reloaded"], ids
    print("  -> agent reload picks up file changes: OK")


# ---------------------------------------------------------------------------
# Unit tests: built-in ops introspection
# ---------------------------------------------------------------------------

def test_builtin_ops_have_required_fields(tmp_dir):
    for op in BUILTIN_OPS:
        assert "id" in op
        assert "name" in op
        assert "params_schema" in op
        assert "ui_hint" in op
        assert "kind" in op["ui_hint"]
    print("  -> all built-in ops have required fields: OK")


def test_is_builtin_recognizes_all(tmp_dir):
    for op in BUILTIN_OPS:
        assert is_builtin(op["id"])
    assert not is_builtin("user.custom")
    print("  -> is_builtin matches all built-ins: OK")


def test_get_builtin_ops_returns_deepcopy(tmp_dir):
    a = get_builtin_ops()
    b = get_builtin_ops()
    a[0]["name"] = "mutated"
    assert b[0]["name"] != "mutated"
    print("  -> get_builtin_ops returns independent copies: OK")


# ---------------------------------------------------------------------------
# Helpers: integration tests
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(url: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1.0).read()
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            time.sleep(0.3)
    return False


_RUNNER_SCRIPT_TEMPLATE = '''
import os, sys, uvicorn
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


class PortalServer:
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
        runner_path = os.path.join(SCRIPT_DIR, "_device_agent_runner.py")
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
        runner_path = os.path.join(SCRIPT_DIR, "_device_agent_runner.py")
        if os.path.exists(runner_path):
            os.remove(runner_path)


def _issue_bootstrap_token(device_id: str, display_name: str) -> str:
    from datetime import datetime, timedelta
    tok_id = str(uuid.uuid4())
    with _test_session_scope() as s:
        s.add(_TestBootstrapToken(
            id=tok_id,
            device_id=device_id,
            display_name=display_name,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        ))
    return tok_id


def _register_device(base: str, device_id: str, display_name: str) -> dict:
    tok = _issue_bootstrap_token(device_id, display_name)
    body = json.dumps({
        "device_id": device_id,
        "display_name": display_name,
        "bootstrap_token": tok,
    }).encode()
    req = urllib.request.Request(
        f"{base}/api/control/devices/register",
        data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Integration tests: agent with real server
# ---------------------------------------------------------------------------

def _drain_until(ws, predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            raw = ws.recv()
        except Exception:
            return None
        msg = json.loads(raw)
        if predicate(msg):
            return msg
    return None


def test_integration_register_and_execute(tmp_dir):
    with PortalServer() as srv:
        info = _register_device(srv.base, "agent-int-1", "Agent Int 1")
        bearer = info["bearer_token"]
        ws_url = f"{srv.ws_base}/api/control/devices/{info['id']}/ws?token={bearer}"

        cfg_path = os.path.join(tmp_dir, "config.json")
        with open(cfg_path, "w") as f:
            json.dump({
                "device_id": info["id"],
                "display_name": info["display_name"],
                "server_url": srv.base,
                "operations": [
                    {
                        "id": "echo.hello",
                        "name": "Echo",
                        "command": ["echo", "hello"],
                        "params_schema": {"type": "object", "properties": {}},
                        "ui_hint": {"kind": "button", "label": "Echo"},
                    },
                ],
            }, f)
        agent = Agent(cfg_path)
        agent.bearer_token = bearer
        agent.device_id = info["id"]
        agent.credentials = {"device_id": info["id"], "bearer_token": bearer}

        async def _scenario():
            async with websockets.connect(ws_url) as ws:
                welcome = json.loads(await ws.recv())
                assert welcome["type"] == "welcome", welcome
                ops = list(BUILTIN_OPS)
                ops.append({
                    "id": "echo.hello", "name": "Echo",
                    "group": "default",
                    "params_schema": {"type": "object", "properties": {}},
                    "ui_hint": {"kind": "button", "label": "Echo"},
                })
                await ws.send(json.dumps({"type": "operations_register", "operations": ops}))
                ack = json.loads(await ws.recv())
                assert ack["type"] == "operations_registered"

                from servers.control_plane.models import DeviceACL
                with _test_session_scope() as s:
                    s.add(DeviceACL(
                        id=str(uuid.uuid4()),
                        source_device=f"device:{info['id']}",
                        target_device=f"device:{info['id']}",
                        operation="echo.hello",
                        extra="",
                    ))

                issue_body = json.dumps({
                    "operation": "echo.hello",
                    "target_device_id": info["id"],
                    "params": {},
                }).encode()
                req = urllib.request.Request(
                    f"{srv.base}/api/control/commands",
                    data=issue_body, method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {bearer}",
                    },
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    issued = json.loads(resp.read())
                cmd_id = issued["id"]
                print(f"  [debug] issued command id={cmd_id[:8]} status={issued['status']}")

                push_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                push = json.loads(push_raw)
                assert push["type"] == "command", push
                assert push["command_id"] == cmd_id

                await ws.send(json.dumps({
                    "type": "claim",
                    "command_id": push["command_id"],
                    "claim_token": push["claim_token"],
                }))
                ack = json.loads(await ws.recv())
                assert ack["type"] == "claimed_ack", ack

                loop = asyncio.get_event_loop()
                op = next(o for o in agent.config["operations"] if o["id"] == "echo.hello")
                body = await loop.run_in_executor(None, agent._run_user_op, op, {})
                assert body["succeeded"], body
                await ws.send(json.dumps({
                    "type": "result",
                    "command_id": push["command_id"],
                    "status": "succeeded",
                    "result": body["result"],
                }))
                result_ack = json.loads(await ws.recv())
                assert result_ack["type"] == "result_ack", result_ack

                await ws.send(json.dumps({"type": "ping"}))
                pong = json.loads(await ws.recv())
                assert pong["type"] == "pong", pong

        import asyncio
        asyncio.run(_scenario())
        print("  -> integration: register + echo via WS: OK")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

import tempfile

def main() -> int:
    print("=" * 60)
    print("Device Agent Tests")
    print("=" * 60)
    print()
    failed = []

    def _run(name, fn):
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                fn(tmp_dir)
            except Exception as e:
                import traceback
                traceback.print_exc()
                failed.append((name, str(e)))

    print("[unit: interpolate / build_command]")
    _run("interpolate_simple", test_interpolate_simple)
    _run("interpolate_quoted", test_interpolate_quoted)
    _run("interpolate_missing_param", test_interpolate_missing_param)
    _run("build_command_list", test_build_command_list)
    _run("build_command_list_with_substitution", test_build_command_list_with_substitution)
    _run("build_command_string_shlex", test_build_command_string_shlex)
    _run("build_command_string_shell", test_build_command_string_shell)
    _run("build_command_list_shell_quoting", test_build_command_list_shell_quoting)
    print()
    print("[unit: validate_params]")
    _run("validate_params_ok", test_validate_params_ok)
    _run("validate_params_multiple_errors", test_validate_params_multiple_errors)
    print()
    print("[unit: execute_shell]")
    _run("execute_shell_success", test_execute_shell_success)
    _run("execute_shell_failure", test_execute_shell_failure)
    _run("execute_shell_timeout", test_execute_shell_timeout)
    print()
    print("[unit: load/save config]")
    _run("load_config_minimal", test_load_config_minimal)
    _run("load_config_invalid", test_load_config_invalid)
    _run("credentials_roundtrip", test_credentials_roundtrip)
    _run("parse_json_field_variants", test_parse_json_field_variants)
    print()
    print("[unit: agent built-in ops]")
    _run("agent_list_operations_empty", test_agent_list_operations_empty)
    _run("agent_add_then_list", test_agent_add_then_list)
    _run("agent_add_duplicate_fails", test_agent_add_duplicate_fails)
    _run("agent_cannot_modify_builtin", test_agent_cannot_modify_builtin)
    _run("agent_update_operation", test_agent_update_operation)
    _run("agent_delete_operation", test_agent_delete_operation)
    _run("agent_test_operation", test_agent_test_operation)
    _run("agent_test_operation_with_params", test_agent_test_operation_with_params)
    _run("agent_test_validation_fails", test_agent_test_validation_fails)
    _run("agent_get_config", test_agent_get_config)
    _run("agent_reload_triggers_event", test_agent_reload_triggers_event)
    _run("agent_reload_picks_up_changes", test_agent_reload_picks_up_changes)
    print()
    print("[unit: built-in ops introspection]")
    _run("builtin_ops_have_required_fields", test_builtin_ops_have_required_fields)
    _run("is_builtin_recognizes_all", test_is_builtin_recognizes_all)
    _run("get_builtin_ops_returns_deepcopy", test_get_builtin_ops_returns_deepcopy)
    print()
    print("[integration: agent with real server]")
    _run("integration_register_and_execute", test_integration_register_and_execute)

    print()
    if failed:
        print(f"!! {len(failed)} test(s) failed:")
        for name, err in failed:
            print(f"   - {name}: {err}")
        return 1
    print("=" * 60)
    print("      ALL DEVICE AGENT TESTS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
