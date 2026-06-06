"""
Portal device agent: a generic process that connects to the control plane via
WebSocket, advertises operations defined in a JSON config, and executes
incoming commands as local shell commands.

Configuration is editable from the portal's WebUI through the built-in
operations in builtin_ops.py. The agent reloads its config on SIGHUP.
"""
import argparse
import asyncio
import copy
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Optional

import jsonschema
import websockets
from websockets.exceptions import (
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidStatus,
    WebSocketException,
)

from .builtin_ops import BUILTIN_OPS, is_builtin


CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "device_id": {"type": "string"},
        "display_name": {"type": "string"},
        "server_url": {"type": "string"},
        "bootstrap_token": {"type": "string"},
        "bootstrap_token_file": {"type": "string"},
        "credentials_file": {"type": "string"},
        "operations": {"type": "array", "items": {"type": "object"}},
    },
}


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _resolve_bootstrap_token(cfg: dict) -> str:
    if cfg.get("bootstrap_token"):
        return cfg["bootstrap_token"].strip()
    p = cfg.get("bootstrap_token_file")
    if not p:
        raise RuntimeError("config must define bootstrap_token or bootstrap_token_file")
    return _read_text(p)


def _load_credentials(path: Optional[str]) -> Optional[dict]:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[device-agent] failed to read credentials from {path}: {e}", file=sys.stderr)
        return None


def _save_credentials(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
        f.write("\n")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    jsonschema.validate(cfg, CONFIG_SCHEMA)
    if "operations" not in cfg:
        cfg["operations"] = []
    if "credentials_file" not in cfg:
        cfg["credentials_file"] = os.path.join(
            os.path.dirname(path) or ".", "credentials.json"
        )
    return cfg


def _http_register(server_url: str, device_id: str, display_name: str, bootstrap_token: str) -> dict:
    body = json.dumps({
        "device_id": device_id,
        "display_name": display_name,
        "bootstrap_token": bootstrap_token,
    }).encode()
    req = urllib.request.Request(
        f"{server_url.rstrip('/')}/api/control/devices/register",
        data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "portal-device-agent",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"register failed: HTTP {e.code} {raw}")


def _build_command(template: Any, params: dict, use_shell: bool) -> tuple[list, bool]:
    """
    Returns (argv_list, run_via_shell).
    - If template is str and use_shell is True: returned as ["sh", "-c", <expanded>] (single argv[2] is the shell line).
    - If template is str and use_shell is False: shlex.split then substitute.
    - If template is list: substitute each element, run as argv (never via shell unless use_shell).
    - Substitution: replace "{name}" with str(params[name]) in each element.
    """
    def _sub(s: str) -> str:
        return _interpolate(s, params)

    if isinstance(template, str):
        if use_shell:
            return ["sh", "-c", _interpolate(template, params, quote=True)], True
        parts = shlex.split(template)
        return [_sub(p) for p in parts], False
    if isinstance(template, list):
        if use_shell:
            line = " ".join(shlex.quote(_sub(str(p))) for p in template)
            return ["sh", "-c", line], True
        return [_sub(str(p)) for p in template], False
    raise RuntimeError(f"command template must be str or list, got {type(template).__name__}")


def _interpolate(template: str, params: dict, *, quote: bool = False) -> str:
    out = []
    i = 0
    while i < len(template):
        ch = template[i]
        if ch == "{" and i + 1 < len(template) and template[i + 1] == "}":
            raise RuntimeError("empty placeholder '{}' in command template")
        if ch == "{" and i + 1 < len(template):
            j = template.find("}", i + 1)
            if j == -1:
                break
            name = template[i + 1:j].strip()
            if name not in params:
                raise RuntimeError(f"command template uses missing param: {name!r}")
            val = str(params[name])
            out.append(shlex.quote(val) if quote else val)
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _validate_params(schema: dict, params: dict) -> None:
    validator = jsonschema.Draft7Validator(schema) if schema else None
    if validator is not None:
        errors = sorted(validator.iter_errors(params), key=lambda e: e.path)
        if errors:
            msgs = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]
            raise RuntimeError("params validation failed: " + "; ".join(msgs))


def _execute_shell(argv: list, shell: bool, timeout: int) -> dict:
    started = time.time()
    try:
        result = subprocess.run(
            argv,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "succeeded": result.returncode == 0,
            "result": {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "duration_ms": int((time.time() - started) * 1000),
            },
        }
    except subprocess.TimeoutExpired:
        return {
            "succeeded": False,
            "error": f"command timed out after {timeout}s",
            "result": {"duration_ms": int((time.time() - started) * 1000)},
        }


def _op_dict(user_op: dict) -> dict:
    spec = {
        "id": user_op["id"],
        "name": user_op.get("name", user_op["id"]),
        "group": user_op.get("group", "default"),
        "description": user_op.get("description"),
        "params_schema": user_op.get("params_schema") or {"type": "object", "properties": {}},
        "ui_hint": user_op.get("ui_hint"),
    }
    return spec


def _all_ops(cfg: dict) -> list:
    return [copy.deepcopy(op) for op in BUILTIN_OPS] + [_op_dict(o) for o in cfg.get("operations", [])]


def _lookup_op(cfg: dict, op_id: str) -> Optional[dict]:
    if is_builtin(op_id):
        for op in BUILTIN_OPS:
            if op["id"] == op_id:
                return copy.deepcopy(op)
    for op in cfg.get("operations", []):
        if op.get("id") == op_id:
            return op
    return None


def _parse_json_field(value: Any, field_name: str) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"{field_name} is not valid JSON: {e}")
    raise RuntimeError(f"{field_name} must be a JSON string or object")


def _materialize_operation(params: dict) -> dict:
    op_id = params.get("id")
    if not op_id:
        raise RuntimeError("id is required")
    if is_builtin(op_id):
        raise RuntimeError(f"cannot modify built-in operation {op_id!r}")
    name = params.get("name")
    if not name:
        raise RuntimeError("name is required")
    command = params.get("command")
    if not command:
        raise RuntimeError("command is required")
    schema = _parse_json_field(params.get("params_schema"), "params_schema") or {"type": "object", "properties": {}}
    ui_hint = _parse_json_field(params.get("ui_hint"), "ui_hint")
    op = {
        "id": op_id,
        "name": name,
        "group": params.get("group", "default"),
        "description": params.get("description") or "",
        "command": command,
        "shell": bool(params.get("shell", False)),
        "timeout_seconds": int(params.get("timeout_seconds", 30)),
        "params_schema": schema,
    }
    if ui_hint is not None:
        op["ui_hint"] = ui_hint
    return op


class Agent:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = load_config(config_path)
        self.credentials = _load_credentials(self.config.get("credentials_file"))
        self.bearer_token: Optional[str] = None
        self.device_id: Optional[str] = None
        self._reload_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._ws: Optional[Any] = None
        self._registered_ops: list = []

    def request_reload(self) -> None:
        self._reload_event.set()

    def request_stop(self) -> None:
        self._stop_event.set()
        self._reload_event.set()

    def reload_config(self) -> None:
        try:
            new_cfg = load_config(self.config_path)
        except Exception as e:
            print(f"[device-agent] reload failed: {e}", file=sys.stderr)
            return
        self.config = new_cfg
        if self.credentials is None:
            self.credentials = _load_credentials(self.config.get("credentials_file"))
        print(f"[device-agent] config reloaded: {len(self.config.get('operations', []))} user ops", file=sys.stderr)

    def _ensure_registered(self) -> str:
        if self.credentials and self.credentials.get("bearer_token") and self.credentials.get("device_id"):
            self.bearer_token = self.credentials["bearer_token"]
            self.device_id = self.credentials["device_id"]
            return self.bearer_token
        token = _resolve_bootstrap_token(self.config)
        info = _http_register(
            self.config["server_url"],
            self.config["device_id"],
            self.config.get("display_name", self.config["device_id"]),
            token,
        )
        self.bearer_token = info["bearer_token"]
        self.device_id = info["id"]
        self.credentials = {
            "device_id": self.device_id,
            "bearer_token": self.bearer_token,
        }
        creds_path = self.config.get("credentials_file")
        if creds_path:
            _save_credentials(creds_path, self.credentials)
            print(f"[device-agent] credentials saved to {creds_path}", file=sys.stderr)
        return self.bearer_token

    async def _register_ops(self, ws) -> None:
        ops = _all_ops(self.config)
        await ws.send(json.dumps({"type": "operations_register", "operations": ops}))
        ack_raw = await ws.recv()
        try:
            ack = json.loads(ack_raw)
        except json.JSONDecodeError:
            print(f"[device-agent] non-JSON ack: {ack_raw!r}", file=sys.stderr)
            return
        if ack.get("type") != "operations_registered":
            print(f"[device-agent] unexpected register ack: {ack}", file=sys.stderr)
            return
        self._registered_ops = ops
        print(f"[device-agent] registered {ack.get('count', 0)} operations", file=sys.stderr)

    async def _send_claim(self, ws, command_id: str, claim_token: str) -> bool:
        await ws.send(json.dumps({"type": "claim", "command_id": command_id, "claim_token": claim_token}))
        try:
            ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
        except asyncio.TimeoutError:
            return False
        return ack.get("type") == "claimed_ack"

    async def _send_result(self, ws, command_id: str, body: dict) -> None:
        await ws.send(json.dumps({"type": "result", "command_id": command_id, **body}))

    def _handle_builtin(self, op_id: str, params: dict) -> dict:
        try:
            if op_id == "device.config.list_operations":
                return {"succeeded": True, "result": {"operations": self.config.get("operations", [])}}
            if op_id == "device.config.add_operation":
                op = _materialize_operation(params)
                existing_ids = [o.get("id") for o in self.config.get("operations", [])]
                if op["id"] in existing_ids:
                    return {"succeeded": False, "error": f"operation {op['id']!r} already exists"}
                self.config.setdefault("operations", []).append(op)
                self._write_config()
                self.request_reload()
                return {"succeeded": True, "result": {"added": op["id"]}}
            if op_id == "device.config.update_operation":
                op = _materialize_operation(params)
                for i, existing in enumerate(self.config.get("operations", [])):
                    if existing.get("id") == op["id"]:
                        self.config["operations"][i] = op
                        self._write_config()
                        self.request_reload()
                        return {"succeeded": True, "result": {"updated": op["id"]}}
                return {"succeeded": False, "error": f"operation {op['id']!r} not found"}
            if op_id == "device.config.delete_operation":
                target = params.get("id")
                if not target:
                    return {"succeeded": False, "error": "id is required"}
                ops = self.config.get("operations", [])
                new_ops = [o for o in ops if o.get("id") != target]
                if len(new_ops) == len(ops):
                    return {"succeeded": False, "error": f"operation {target!r} not found"}
                self.config["operations"] = new_ops
                self._write_config()
                self.request_reload()
                return {"succeeded": True, "result": {"deleted": target}}
            if op_id == "device.config.test_operation":
                target = params.get("id")
                if not target:
                    return {"succeeded": False, "error": "id is required"}
                op = _lookup_op(self.config, target)
                if op is None:
                    return {"succeeded": False, "error": f"operation {target!r} not found"}
                test_params = _parse_json_field(params.get("params"), "params") or {}
                return self._run_user_op(op, test_params)
            if op_id == "device.config.get_config":
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        text = f.read()
                except OSError as e:
                    return {"succeeded": False, "error": f"read config failed: {e}"}
                return {"succeeded": True, "result": {"config": text, "path": self.config_path}}
            if op_id == "device.config.reload":
                self.request_reload()
                return {"succeeded": True, "result": {"reloaded": True}}
            return {"succeeded": False, "error": f"unknown built-in operation: {op_id!r}"}
        except RuntimeError as e:
            return {"succeeded": False, "error": str(e)}

    def _run_user_op(self, op: dict, params: dict) -> dict:
        try:
            _validate_params(op.get("params_schema") or {}, params)
            argv, shell = _build_command(op["command"], params, bool(op.get("shell", False)))
            timeout = int(op.get("timeout_seconds", 30))
        except RuntimeError as e:
            return {"succeeded": False, "error": str(e)}
        return _execute_shell(argv, shell, timeout)

    def _write_config(self) -> None:
        ops_only = {
            k: v for k, v in self.config.items()
            if k in ("device_id", "display_name", "server_url", "bootstrap_token",
                     "bootstrap_token_file", "credentials_file", "operations")
        }
        tmp = self.config_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ops_only, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, self.config_path)
        try:
            os.chmod(self.config_path, 0o600)
        except OSError:
            pass

    async def _process_command(self, ws, msg: dict) -> None:
        cid = msg["command_id"]
        ctok = msg.get("claim_token")
        op_id = msg.get("operation")
        params = msg.get("params") or {}
        ok = await self._send_claim(ws, cid, ctok)
        if not ok:
            print(f"[device-agent] claim failed for {cid[:8]}", file=sys.stderr)
            return
        print(f"[device-agent] executing {op_id} (id={cid[:8]})", file=sys.stderr)
        loop = asyncio.get_event_loop()
        if is_builtin(op_id):
            body = await loop.run_in_executor(None, self._handle_builtin, op_id, params)
        else:
            op = _lookup_op(self.config, op_id)
            if op is None:
                body = {"succeeded": False, "error": f"operation {op_id!r} not registered locally"}
            else:
                body = await loop.run_in_executor(None, self._run_user_op, op, params)
        status = body.pop("status", None)
        if status is None:
            status = "succeeded" if body.get("succeeded") else "failed"
        await self._send_result(ws, cid, {
            "status": status,
            "result": body.get("result"),
            "error": body.get("error"),
        })

    async def _serve(self, ws) -> None:
        await self._register_ops(ws)
        while True:
            if self._reload_event.is_set():
                self.reload_config()
                try:
                    await self._register_ops(ws)
                except Exception as e:
                    print(f"[device-agent] re-register failed: {e}", file=sys.stderr)
                    raise
                self._reload_event.clear()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")
            if mtype == "ping":
                await ws.send(json.dumps({"type": "pong"}))
            elif mtype == "command":
                try:
                    await self._process_command(ws, msg)
                except Exception as e:
                    print(f"[device-agent] process_command error: {e}", file=sys.stderr)
            elif mtype == "bye":
                print(f"[device-agent] server said bye: {msg.get('reason')}", file=sys.stderr)
                return

    async def _run_forever(self) -> None:
        self._ensure_registered()
        ws_base = self.config["server_url"].rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_base}/api/control/devices/{self.device_id}/ws?token={self.bearer_token}"
        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(ws_url) as ws:
                    self._ws = ws
                    print(f"[device-agent] connected to {ws_url}", file=sys.stderr)
                    backoff = 1.0
                    await self._serve(ws)
            except (ConnectionClosedError, ConnectionClosedOK):
                print("[device-agent] connection closed, reconnecting...", file=sys.stderr)
            except (InvalidStatus, WebSocketException, OSError) as e:
                print(f"[device-agent] connection error: {e}, retrying in {backoff:.1f}s", file=sys.stderr)
            except Exception as e:
                print(f"[device-agent] unexpected error: {e}", file=sys.stderr)
            if self._stop_event.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def _on_sighup(*_):
            print("[device-agent] SIGHUP received, scheduling reload", file=sys.stderr)
            self.request_reload()

        def _on_sigterm(*_):
            print("[device-agent] signal received, shutting down", file=sys.stderr)
            self.request_stop()
            try:
                if self._ws is not None:
                    loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self._ws.close()))
            except Exception:
                pass

        for sig, handler in ((signal.SIGHUP, _on_sighup), (signal.SIGTERM, _on_sigterm), (signal.SIGINT, _on_sigterm)):
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass

        try:
            loop.run_until_complete(self._run_forever())
        finally:
            loop.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Portal control-plane device agent")
    parser.add_argument("--config", required=True, help="Path to config.json")
    args = parser.parse_args()
    agent = Agent(args.config)
    agent.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
