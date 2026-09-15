#!/usr/bin/env python3
"""
portal-opencode-tool: thin CLI invoked by the generic device agent to provide
the OpenCode (app-portal feedback) operations.

Each invocation prints a single JSON object to stdout. The device agent returns
that as `result.stdout`, and the portal parses it. Keeping this as a CLI (rather
than a dedicated long-running bridge) lets a single `portal-device-agent` serve
all of a device's operations.

Environment / flags:
  --opencode-url     OpenCode server base URL (env OPENCODE_URL, default
                     http://127.0.0.1:12000)
  --webui-base-url   Browser-facing WebUI base URL for deep links (env
                     OPENCODE_WEBUI_BASE_URL, defaults to --opencode-url)
"""
import argparse
import json
import os
import sys

from .opencode_ops import DEFAULT_OPENCODE_URL, OpenCodeOps


def _make_ops(args) -> OpenCodeOps:
    opencode_url = args.opencode_url or os.environ.get("OPENCODE_URL", DEFAULT_OPENCODE_URL)
    webui = args.webui_base_url or os.environ.get("OPENCODE_WEBUI_BASE_URL")
    return OpenCodeOps(opencode_url, webui)


def _emit(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="portal-opencode-tool", description=__doc__)
    parser.add_argument("--opencode-url", default=None)
    parser.add_argument("--webui-base-url", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    fb = sub.add_parser("feedback", help="Inject a feedback prompt into a pinned session")
    fb.add_argument("--session-id", required=True, dest="session_id")
    fb.add_argument("--prompt", required=True)

    ls = sub.add_parser("list-sessions", help="List OpenCode sessions")
    ls.add_argument("--directory", default=None)

    sub.add_parser("webui-url", help="Print the WebUI base URL and server key")
    sub.add_parser("traits", help="Print the opencode-bridge trait (operation keys + WebUI info)")

    args = parser.parse_args(argv)
    ops = _make_ops(args)

    try:
        if args.command == "feedback":
            return _emit(ops.inject_feedback(args.session_id, args.prompt))
        if args.command == "list-sessions":
            return _emit(ops.list_sessions(args.directory))
        if args.command == "webui-url":
            return _emit({"webui_base_url": ops.webui_base_url, "server_key": ops.server_key})
        if args.command == "traits":
            return _emit(ops.traits())
    except Exception as e:  # noqa: BLE001 - report the failure as JSON on stderr
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
