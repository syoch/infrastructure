"""
Shared OpenCode helpers used by the app-portal helper CLI (portal-opencode-tool).

The portal no longer ships a purpose-specific long-running bridge: a generic
`portal-device-agent` executes configured operations, and the OpenCode-specific
logic lives here and is invoked as shell commands by those operations.
"""
import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

DEFAULT_OPENCODE_URL = "http://127.0.0.1:12000"

# Role -> operation id convention advertised via the `opencode-bridge` trait.
ROLE_KEYS = {
    "feedback": "opencode.feedback",
    "list_sessions": "opencode.list_sessions",
    "webui_url": "opencode.webui_url",
}

TRAITS_OPERATION_ID = "traits.opencode-bridge"


def server_key_for(base_url: str) -> str:
    """Mirrors the OpenCode WebUI server key: base64url(origin) without padding."""
    return base64.urlsafe_b64encode(base_url.encode("utf-8")).decode("ascii").rstrip("=")


def _http_json(url: str, method: str = "GET", body: Optional[dict[str, Any]] = None,
               headers: Optional[dict[str, str]] = None, timeout: float = 10.0) -> tuple[int, Any]:
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


class OpenCodeOps:
    def __init__(self, opencode_url: str = DEFAULT_OPENCODE_URL,
                 webui_base_url: Optional[str] = None):
        self.opencode_url = opencode_url.rstrip("/")
        self.webui_base_url = (webui_base_url or opencode_url).rstrip("/")
        self.server_key = server_key_for(self.webui_base_url)

    def webui_url(self, session_id: str) -> str:
        return f"{self.webui_base_url}/server/{self.server_key}/session/{session_id}"

    def inject_feedback(self, session_id: str, prompt: str) -> dict[str, Any]:
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

    def list_sessions(self, directory: Optional[str] = None) -> dict[str, Any]:
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

    def traits(self) -> dict[str, Any]:
        return {
            "trait": "opencode-bridge",
            "operations": dict(ROLE_KEYS),
            "keys": list(ROLE_KEYS.values()),
            "webui_base_url": self.webui_base_url,
            "server_key": self.server_key,
        }
