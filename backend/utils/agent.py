import json
import urllib.error
import urllib.request
from typing import Any, Optional, cast


def register_device(
    server_url: str,
    device_id: str,
    display_name: str,
    bootstrap_token: str,
    user_agent: Optional[str] = None,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if user_agent:
        headers["User-Agent"] = user_agent
    body = json.dumps({
        "device_id": device_id,
        "display_name": display_name,
        "bootstrap_token": bootstrap_token,
    }).encode()
    req = urllib.request.Request(
        f"{server_url.rstrip('/')}/api/control/devices/register",
        data=body, method="POST", headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return cast(dict[str, Any], json.loads(resp.read()))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"register failed: HTTP {e.code} {raw}")


class ReconnectBackoff:
    def __init__(self, initial: float = 1.0, factor: float = 2.0, maximum: float = 30.0):
        self.initial = initial
        self.factor = factor
        self.maximum = maximum
        self._delay = initial

    def reset(self) -> None:
        self._delay = self.initial

    def next_delay(self) -> float:
        delay = self._delay
        self._delay = min(self._delay * self.factor, self.maximum)
        return delay
