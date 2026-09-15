# Command result waiting (control plane)

`servers/control_plane/core.py:wait_for_command_result(db, command_id, timeout, poll_interval=0.5)`
blocks a worker thread until the command reaches a terminal status
(`TERMINAL_COMMAND_STATUSES = succeeded|failed|timeout|cancelled`) or the timeout elapses.

- Event-driven: `publish_command_status(cmd)` calls `_notify_command_waiters(cmd.id)`, which sets a
  per-command `threading.Event`, so waiters wake immediately on claim/result instead of polling.
  The notify happens BEFORE the `asyncio.get_running_loop()` guard (so it also fires when called
  from a non-loop thread).
- Falls back to a bounded `Event.wait(min(remaining, poll_interval))` so direct-DB test updates
  (which never publish) still resolve.
- Used by `servers/app_portal/api.py:_opencode_meta` to synchronously resolve the `opencode-bridge`
  trait in `GET /apps/{slug}` and `POST /apps/{slug}/feedback`. That synchronous contract is
  asserted by `tests/backend/test_app_portal_delivery_e2e.py`; do not make these routes async
  without also moving the sync SQLAlchemy work off the event loop.
- No `time.sleep` remains in `servers/`.
