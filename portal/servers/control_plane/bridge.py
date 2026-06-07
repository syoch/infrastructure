#!/usr/bin/env python3
"""
Bridge process that connects to the portal control plane and serves
acl.* / device_admin.* operations by invoking the portal-manage CLI.

This is the dogfooding pattern: the server itself does not provide any
operations; the bridge is just a regular device that happens to expose
ACL and device admin operations.
"""
import argparse
import asyncio
import json
import os
import secrets
import shlex
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
import logging
from datetime import datetime, timezone
from typing import Optional

import websockets
from websockets.exceptions import (
    ConnectionClosedError, ConnectionClosedOK, InvalidStatus, WebSocketException,
)

logger = logging.getLogger("portal-bridge")

BRIDGE_DEVICE_ID = "bridge"
BRIDGE_DISPLAY_NAME = "Portal Bridge"

BRIDGE_DEVICE_ID = "bridge"
BRIDGE_DISPLAY_NAME = "Portal Bridge"

BRIDGE_OPERATIONS = [
    {
        "id": "acl.list",
        "name": "acl.list",
        "group": "acl",
        "description": "List all ACL rules",
        "ui_hint": {"kind": "button", "label": "List ACLs"},
        "params_schema": {"type": "object", "properties": {}},
    },
    {
        "id": "acl.create",
        "name": "acl.create",
        "group": "acl",
        "description": "Create a new ACL rule",
        "ui_hint": {"kind": "form", "label": "Create ACL"},
        "params_schema": {
            "type": "object",
            "required": ["source_device", "target_device", "operation"],
            "properties": {
                "source_device": {"type": "string", "title": "Source device", "description": "device:<regex>"},
                "target_device": {"type": "string", "title": "Target device", "description": "device:<regex>"},
                "operation": {"type": "string", "title": "Operation regex", "description": "Operation name or regex"},
                "extra": {"type": "string", "title": "Extra (optional)"},
            },
        },
    },
    {
        "id": "acl.update",
        "name": "acl.update",
        "group": "acl",
        "description": "Update an existing ACL rule",
        "ui_hint": {"kind": "form", "label": "Update ACL"},
        "params_schema": {
            "type": "object",
            "required": ["acl_id"],
            "properties": {
                "acl_id": {"type": "string", "title": "ACL ID"},
                "source_device": {"type": "string", "title": "Source device"},
                "target_device": {"type": "string", "title": "Target device"},
                "operation": {"type": "string", "title": "Operation"},
                "extra": {"type": "string", "title": "Extra"},
            },
        },
    },
    {
        "id": "acl.delete",
        "name": "acl.delete",
        "group": "acl",
        "description": "Delete an ACL rule by id",
        "ui_hint": {"kind": "form", "label": "Delete ACL"},
        "params_schema": {
            "type": "object",
            "required": ["acl_id"],
            "properties": {"acl_id": {"type": "string", "title": "ACL ID"}},
        },
    },
    {
        "id": "device.list",
        "name": "device.list",
        "group": "device_admin",
        "description": "List all registered devices",
        "ui_hint": {"kind": "button", "label": "List Devices"},
        "params_schema": {"type": "object", "properties": {}},
    },
    {
        "id": "device.rename",
        "name": "device.rename",
        "group": "device_admin",
        "description": "Rename a device",
        "ui_hint": {"kind": "form", "label": "Rename Device"},
        "params_schema": {
            "type": "object",
            "required": ["device_id", "display_name"],
            "properties": {
                "device_id": {"type": "string", "title": "Device ID"},
                "display_name": {"type": "string", "title": "Display name"},
            },
        },
    },
    {
        "id": "device.set_admin",
        "name": "device.set_admin",
        "group": "device_admin",
        "description": "Promote a device to admin (or demote)",
        "ui_hint": {"kind": "form", "label": "Set Admin"},
        "params_schema": {
            "type": "object",
            "required": ["device_id", "is_first_webui_device"],
            "properties": {
                "device_id": {"type": "string", "title": "Device ID"},
                "is_first_webui_device": {"type": "boolean", "title": "Admin?"},
            },
        },
    },
    {
        "id": "device.delete",
        "name": "device.delete",
        "group": "device_admin",
        "description": "Delete a device",
        "ui_hint": {"kind": "form", "label": "Delete Device"},
        "params_schema": {
            "type": "object",
            "required": ["device_id"],
            "properties": {"device_id": {"type": "string", "title": "Device ID"}},
        },
    },
]


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


def _run_cli(manage_bin: str, config_path: Optional[str], args: list) -> tuple[int, str, str]:
    cmd = [manage_bin]
    if config_path:
        cmd.extend(["--config", config_path])
    cmd.append("control")
    cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "portal-manage timeout (30s)"
    except FileNotFoundError:
        return 127, "", f"portal-manage not found at {manage_bin!r}"


def _execute_operation(operation: str, params: dict, manage_bin: str, config_path: Optional[str]) -> dict:
    if operation == "acl.list":
        rc, out, err = _run_cli(manage_bin, config_path, ["list-acl"])
        if rc != 0:
            return {"succeeded": False, "error": err.strip() or out.strip() or f"exit={rc}"}
        return {"succeeded": True, "result": {"output": out.strip()}}
    if operation == "acl.create":
        args = ["grant",
                "--source", params.get("source_device", ""),
                "--target", params.get("target_device", ""),
                "--operation", params.get("operation", "")]
        if params.get("extra"):
            args.extend(["--extra", params["extra"]])
        rc, out, err = _run_cli(manage_bin, config_path, args)
        if rc != 0:
            return {"succeeded": False, "error": err.strip() or out.strip() or f"exit={rc}"}
        return {"succeeded": True, "result": {"output": out.strip() or "ok"}}
    if operation == "acl.update":
        acl_id = params.get("acl_id")
        if not acl_id:
            return {"succeeded": False, "error": "acl_id required"}
        args = ["revoke", "--acl-id", acl_id]
        rc, out, err = _run_cli(manage_bin, config_path, args)
        if rc != 0:
            return {"succeeded": False, "error": f"revoke failed: {err.strip() or out.strip()}"}
        args = ["grant",
                "--source", params.get("source_device", ""),
                "--target", params.get("target_device", ""),
                "--operation", params.get("operation", "")]
        if params.get("extra"):
            args.extend(["--extra", params["extra"]])
        rc, out, err = _run_cli(manage_bin, config_path, args)
        if rc != 0:
            return {"succeeded": False, "error": err.strip() or out.strip() or f"exit={rc}"}
        return {"succeeded": True, "result": {"output": "ok"}}
    if operation == "acl.delete":
        acl_id = params.get("acl_id")
        if not acl_id:
            return {"succeeded": False, "error": "acl_id required"}
        rc, out, err = _run_cli(manage_bin, config_path, ["revoke", "--acl-id", acl_id])
        if rc != 0:
            return {"succeeded": False, "error": err.strip() or out.strip() or f"exit={rc}"}
        return {"succeeded": True, "result": {"output": "ok"}}
    if operation == "device.list":
        rc, out, err = _run_cli(manage_bin, config_path, ["list-devices"])
        if rc != 0:
            return {"succeeded": False, "error": err.strip() or out.strip() or f"exit={rc}"}
        return {"succeeded": True, "result": {"output": out.strip()}}
    if operation == "device.rename":
        rc, out, err = _run_cli(manage_bin, config_path, [
            "rename-device",
            "--device-id", params.get("device_id", ""),
            "--display-name", params.get("display_name", ""),
        ])
        if rc != 0:
            return {"succeeded": False, "error": err.strip() or out.strip() or f"exit={rc}"}
        return {"succeeded": True, "result": {"output": "ok"}}
    if operation == "device.set_admin":
        is_admin = bool(params.get("is_first_webui_device"))
        sub = "set-admin" if is_admin else "clear-admin"
        rc, out, err = _run_cli(manage_bin, config_path, [sub, "--device-id", params.get("device_id", "")])
        if rc != 0:
            return {"succeeded": False, "error": err.strip() or out.strip() or f"exit={rc}"}
        return {"succeeded": True, "result": {"output": "ok"}}
    if operation == "device.delete":
        rc, out, err = _run_cli(manage_bin, config_path, ["delete-device", "--device-id", params.get("device_id", "")])
        if rc != 0:
            return {"succeeded": False, "error": err.strip() or out.strip() or f"exit={rc}"}
        return {"succeeded": True, "result": {"output": "ok"}}
    return {"succeeded": False, "error": f"unknown operation: {operation!r}"}


async def _run(server_url: str, ws_url: str, bearer_token: str, manage_bin: str, config_path: Optional[str]) -> None:
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                logger.info(f"connected to {ws_url}")
                backoff = 1.0
                await _serve(ws, bearer_token, manage_bin, config_path)
        except (ConnectionClosedError, ConnectionClosedOK):
            logger.info("connection closed, reconnecting...")
        except (InvalidStatus, WebSocketException, OSError) as e:
            logger.warning(f"connection error: {e}, retrying in {backoff:.1f}s")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30.0)


async def _serve(ws, bearer_token: str, manage_bin: str, config_path: Optional[str]) -> None:
    await ws.send(json.dumps({"type": "operations_register", "operations": BRIDGE_OPERATIONS}))
    ack = json.loads(await ws.recv())
    if ack.get("type") != "operations_registered":
        logger.error(f"unexpected ack: {ack}")
        return
    logger.info(f"registered {ack.get('count', 0)} operations")

    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        mtype = msg.get("type")
        if mtype == "ping":
            await ws.send(json.dumps({"type": "pong"}))
        elif mtype == "command":
            cid = msg["command_id"]
            ctok = msg["claim_token"]
            op = msg["operation"]
            params = msg.get("params", {})
            await ws.send(json.dumps({"type": "claim", "command_id": cid, "claim_token": ctok}))
            try:
                ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
                if ack.get("type") != "claimed_ack":
                    logger.error(f"claim failed: {ack}")
                    continue
            except asyncio.TimeoutError:
                logger.error(f"claim ack timeout for {cid}")
                continue

            logger.info(f"executing {op} (id={cid[:8]})")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, _execute_operation, op, params, manage_bin, config_path,
            )
            status = "succeeded" if result.get("succeeded") else "failed"
            await ws.send(json.dumps({
                "type": "result",
                "command_id": cid,
                "status": status,
                "result": result.get("result"),
                "error": result.get("error"),
            }))


def main() -> int:
    parser = argparse.ArgumentParser(description="Portal control-plane bridge")
    parser.add_argument("--server-url", required=True, help="e.g. http://127.0.0.1:8000")
    parser.add_argument("--bootstrap-token", required=True, help="Bootstrap token issued by portal-manage")
    parser.add_argument("--config", help="Path to portal config.json (for portal-manage invocations)")
    parser.add_argument("--device-id", default=BRIDGE_DEVICE_ID)
    parser.add_argument("--display-name", default=BRIDGE_DISPLAY_NAME)
    parser.add_argument("--manage-bin", default=os.environ.get("PORTAL_MANAGE_BIN", "portal-manage"))
    args = parser.parse_args()

    ws_base = args.server_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
    logger.info(f"registering device {args.device_id!r} via bootstrap token")
    info = _http_register(args.server_url, args.device_id, args.display_name, args.bootstrap_token)
    bearer_token = info["bearer_token"]
    logger.info(f"registered; id={info['id']} admin={info.get('is_first_webui_device', False)}")

    ws_url = f"{ws_base}/api/control/devices/{info['id']}/ws?token={bearer_token}"

    stop = asyncio.Event()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _on_signal(*_):
        logger.info("received signal, shutting down")
        stop.set()
        loop.stop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            pass

    try:
        loop.run_until_complete(_run(args.server_url, ws_url, bearer_token, args.manage_bin, args.config))
    finally:
        loop.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
