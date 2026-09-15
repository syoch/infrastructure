#!/usr/bin/env python3
"""
Bridge process that connects to the portal control plane and serves
opencode.* operations by talking to a local OpenCode server.

It reuses the control-plane device channel (register + WebSocket claim/result)
so feedback submitted on the App Portal reaches the pinned OpenCode session on
the machine where OpenCode actually runs.

Operations:
  - opencode.feedback        : inject a feedback prompt into a session (async)
  - opencode.list_sessions   : list sessions for a project directory
  - opencode.webui_url       : report the WebUI base URL + server key
"""
import argparse
import asyncio
import base64
import json
import logging
import os
import signal
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

import websockets
from websockets.exceptions import (
    ConnectionClosedError, ConnectionClosedOK, InvalidStatus, WebSocketException,
)

logger = logging.getLogger("opencode-bridge")

BRIDGE_DEVICE_ID = "opencode-bridge"
BRIDGE_DISPLAY_NAME = "OpenCode Bridge"
DEFAULT_OPENCODE_URL = "http://127.0.0.1:12000"


def server_key_for(base_url: str) -> str:
    return base64.urlsafe_b64encode(base_url.encode("utf-8")).decode("ascii").rstrip("=")


BRIDGE_OPERATIONS = [
    {
        "id": "opencode.feedback",
        "name": "opencode.feedback",
        "group": "opencode",
        "description": "Inject a feedback prompt into a pinned OpenCode session",
        "ui_hint": {"kind": "form", "label": "Send Feedback"},
        "params_schema": {
            "type": "object",
            "required": ["session_id", "prompt"],
            "properties": {
                "session_id": {"type": "string", "title": "Session ID"},
                "prompt": {"type": "string", "title": "Prompt", "ui_hint": {"widget": "textarea"}},
                "app_slug": {"type": "string", "title": "App slug"},
            },
        },
        "result_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "webui_url": {"type": "string"},
            },
        },
    },
    {
        "id": "opencode.list_sessions",
        "name": "opencode.list_sessions",
        "group": "opencode",
        "description": "List OpenCode sessions (optionally filtered by directory)",
        "ui_hint": {"kind": "form", "label": "List Sessions"},
        "params_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "title": "Directory (optional)"},
            },
        },
    },
    {
        "id": "opencode.webui_url",
        "name": "opencode.webui_url",
        "group": "opencode",
        "description": "Report the OpenCode WebUI base URL and server key",
        "ui_hint": {"kind": "button", "label": "WebUI URL"},
        "params_schema": {"type": "object", "properties": {}},
    },
]


# --- HTTP helpers ---

def _http_json(url: str, method: str = "GET", body: Optional[dict] = None,
               headers: Optional[dict] = None, timeout: float = 10.0):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"} if body is not None else {}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if not raw:
            return resp.status, None
        return resp.status, json.loads(raw)


def _http_register(server_url: str, device_id: str, display_name: str, bootstrap_token: str) -> dict:
    body = json.dumps({
        "device_id": device_id,
        "display_name": display_name,
        "bootstrap_token": bootstrap_token,
    }).encode()
    req = urllib.request.Request(
        f"{server_url.rstrip('/')}/api/control/devices/register",
        data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"register failed: HTTP {e.code} {raw}")


def _load_credentials(path: Optional[str]) -> Optional[dict]:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"failed to read credentials from {path}: {e}")
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


def _resolve_bootstrap_token(arg_token: Optional[str], token_file: Optional[str]) -> str:
    if arg_token:
        return arg_token
    if token_file:
        with open(token_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    raise SystemExit("--bootstrap-token or --bootstrap-token-file is required when no cached credentials exist")


# --- OpenCode operations ---

class OpenCodeOps:
    def __init__(self, opencode_url: str, webui_base_url: str):
        self.opencode_url = opencode_url.rstrip("/")
        self.webui_base_url = webui_base_url.rstrip("/")
        self.server_key = server_key_for(self.webui_base_url)

    def webui_url(self, session_id: str) -> str:
        return f"{self.webui_base_url}/server/{self.server_key}/session/{session_id}"

    def inject_feedback(self, session_id: str, prompt: str) -> dict:
        status, _ = _http_json(
            f"{self.opencode_url}/session/{urllib.parse.quote(session_id)}/prompt_async",
            method="POST",
            body={"parts": [{"type": "text", "text": prompt}]},
            timeout=30.0,
        )
        return {
            "session_id": session_id,
            "webui_url": self.webui_url(session_id),
            "accepted": status in (200, 202, 204),
        }

    def list_sessions(self, directory: Optional[str] = None) -> dict:
        _, data = _http_json(f"{self.opencode_url}/session", method="GET", timeout=10.0)
        sessions = data or []
        if directory:
            sessions = [s for s in sessions if (s.get("directory") or "") == directory]
        return {
            "sessions": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "directory": s.get("directory"),
                    "projectID": s.get("projectID"),
                    "agent": s.get("agent"),
                }
                for s in sessions
            ]
        }


def _execute_operation(ops: OpenCodeOps, operation: str, params: dict) -> dict:
    if operation == "opencode.feedback":
        session_id = params.get("session_id")
        prompt = params.get("prompt")
        if not session_id or not prompt:
            return {"succeeded": False, "error": "session_id and prompt are required"}
        try:
            result = ops.inject_feedback(session_id, prompt)
            return {"succeeded": True, "result": result}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            return {"succeeded": False, "error": f"opencode HTTP {e.code}: {raw}"}
        except Exception as e:  # noqa: BLE001 - report any transport failure back to the portal
            return {"succeeded": False, "error": f"opencode request failed: {e}"}
    if operation == "opencode.list_sessions":
        try:
            return {"succeeded": True, "result": ops.list_sessions(params.get("directory"))}
        except Exception as e:  # noqa: BLE001
            return {"succeeded": False, "error": f"opencode request failed: {e}"}
    if operation == "opencode.webui_url":
        return {
            "succeeded": True,
            "result": {"webui_base_url": ops.webui_base_url, "server_key": ops.server_key},
        }
    return {"succeeded": False, "error": f"unknown operation: {operation!r}"}


# --- Bridge loop ---

async def _run(server_url: str, ws_url: str, ops: OpenCodeOps, bearer_token: str, stop: asyncio.Event) -> None:
    backoff = 1.0
    while not stop.is_set():
        try:
            async with websockets.connect(ws_url) as ws:
                logger.info(f"connected to {ws_url}")
                backoff = 1.0
                await _serve(server_url, ws, ops, bearer_token, stop)
        except (ConnectionClosedError, ConnectionClosedOK):
            logger.info("connection closed, reconnecting...")
        except (InvalidStatus, WebSocketException, OSError) as e:
            logger.warning(f"connection error: {e}, retrying in {backoff:.1f}s")
        if stop.is_set():
            break
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30.0)


async def _announce(server_url: str, bearer_token: str, ops: OpenCodeOps) -> None:
    def _do():
        try:
            _http_json(
                f"{server_url.rstrip('/')}/api/app-portal/bridges/announce",
                method="POST",
                body={
                    "webui_base_url": ops.webui_base_url,
                    "server_key": ops.server_key,
                    "hostname": os.uname().nodename,
                },
                headers={"Authorization": f"Bearer {bearer_token}"},
                timeout=10.0,
            )
            logger.info(f"announced webui_base_url={ops.webui_base_url}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"bridge announce failed: {e}")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _do)


async def _consume_welcome(ws) -> list:
    raw = await ws.recv()
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"non-JSON welcome: {raw!r}")
        return []
    if msg.get("type") != "welcome":
        logger.warning(f"unexpected first message: {msg.get('type')!r}")
        return []
    pending = msg.get("pending_commands") or []
    if pending:
        logger.info(f"welcome: {len(pending)} pending command(s)")
    return pending


async def _register_ops(ws) -> None:
    await ws.send(json.dumps({"type": "operations_register", "operations": BRIDGE_OPERATIONS}))
    ack = json.loads(await ws.recv())
    if ack.get("type") != "operations_registered":
        logger.error(f"unexpected register ack: {ack}")
        return
    logger.info(f"registered {ack.get('count', 0)} operations")


async def _process_command(ws, ops: OpenCodeOps, msg: dict) -> None:
    cid = msg["command_id"]
    ctok = msg["claim_token"]
    op = msg["operation"]
    params = msg.get("params", {})
    await ws.send(json.dumps({"type": "claim", "command_id": cid, "claim_token": ctok}))
    try:
        ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
        if ack.get("type") != "claimed_ack":
            logger.error(f"claim failed: {ack}")
            return
    except asyncio.TimeoutError:
        logger.error(f"claim ack timeout for {cid}")
        return

    logger.info(f"executing {op} (id={cid[:8]})")
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _execute_operation, ops, op, params)
    status = "succeeded" if result.get("succeeded") else "failed"
    await ws.send(json.dumps({
        "type": "result",
        "command_id": cid,
        "status": status,
        "result": result.get("result"),
        "error": result.get("error"),
    }))


async def _serve(server_url: str, ws, ops: OpenCodeOps, bearer_token: str, stop: asyncio.Event) -> None:
    await _announce(server_url, bearer_token, ops)
    pending = await _consume_welcome(ws)
    await _register_ops(ws)
    for cmd in pending:
        await _process_command(ws, ops, cmd)

    while not stop.is_set():
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
            await _process_command(ws, ops, msg)
        elif mtype == "bye":
            logger.info("server said bye")
            return


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [opencode-bridge] %(message)s")
    parser = argparse.ArgumentParser(description="Portal app-portal OpenCode bridge")
    parser.add_argument("--server-url", required=True, help="e.g. http://127.0.0.1:8000")
    parser.add_argument("--bootstrap-token", help="Bootstrap token issued by portal-manage (first run only)")
    parser.add_argument("--bootstrap-token-file", default=None,
                        help="File containing the bootstrap token (alternative to --bootstrap-token)")
    parser.add_argument("--credentials-file", default=None,
                        help="Persist the registered device credentials here so restarts reuse them")
    parser.add_argument("--device-id", default=BRIDGE_DEVICE_ID)
    parser.add_argument("--display-name", default=BRIDGE_DISPLAY_NAME)
    parser.add_argument("--opencode-url", default=os.environ.get("OPENCODE_URL", DEFAULT_OPENCODE_URL))
    parser.add_argument("--webui-base-url", default=None,
                        help="Base URL of the OpenCode WebUI (defaults to --opencode-url)")
    args = parser.parse_args()

    webui_base_url = args.webui_base_url or args.opencode_url
    ops = OpenCodeOps(args.opencode_url, webui_base_url)

    ws_base = args.server_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")

    credentials = _load_credentials(args.credentials_file)
    if credentials and credentials.get("device_id") and credentials.get("bearer_token"):
        device_id = credentials["device_id"]
        bearer_token = credentials["bearer_token"]
        logger.info(f"using cached credentials for device {device_id!r}")
    else:
        token = _resolve_bootstrap_token(args.bootstrap_token, args.bootstrap_token_file)
        logger.info(f"registering device {args.device_id!r} via bootstrap token")
        info = _http_register(args.server_url, args.device_id, args.display_name, token)
        device_id = info["id"]
        bearer_token = info["bearer_token"]
        if args.credentials_file:
            _save_credentials(args.credentials_file, {"device_id": device_id, "bearer_token": bearer_token})
            logger.info(f"credentials saved to {args.credentials_file}")
        logger.info(f"registered; id={device_id}")

    ws_url = f"{ws_base}/api/control/devices/{device_id}/ws?token={bearer_token}"

    stop = asyncio.Event()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _request_stop():
        logger.info("received signal, shutting down")
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (ValueError, OSError):
            pass

    try:
        loop.run_until_complete(_run(args.server_url, ws_url, ops, bearer_token, stop))
    finally:
        loop.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
