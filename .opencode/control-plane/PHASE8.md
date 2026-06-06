# Phase 8 — Backup/Restore Verification for Control Plane

**Status**: DONE

## Goal
Verify that `backup_data()` captures all 5 control plane tables, and that
`restore_backup_tarball(strategy=...)` works for both `overwrite` and `merge`
strategies.

## Files added
- `portal/tests/backend/test_control_plane_backup.py`

## Test cases
1. **`test_backup_captures_all_tables`** — populates all 5 tables with known
   data, calls `ext.backup_data(session)`, asserts all 5 expected keys are
   present with the right row counts.
2. **`test_backup_restore_via_tarball`** — creates a tarball via
   `BackupManager.create_backup_tarball()`, deletes all 5 tables, restores via
   `restore_backup_tarball(strategy="overwrite")`, asserts all rows came back
   with the original field values.
3. **`test_backup_merge_preserves_existing`** — creates backup A, then adds
   `extra-device` + an extra ACL, then deletes `bkp-device-1` (so DB has
   `webui` + `extra-device`), then restores A with `strategy="merge"`.
   Asserts: `bkp-device-1` is re-added from backup, `extra-device` is
   preserved, all related ACL/op/token/command rows are correct.

## Key findings
- SQLAlchemy's unit-of-work does not auto-sort inserts by FK dependency when
  `session.add()` calls are interleaved with sub-object creation. Workaround:
  call `session.flush()` after adding parent rows (Device) before adding child
  rows (CommandRequest) that FK-reference them.
- SQLAlchemy `Query.delete()` does not delete from tables that have FKs
  pointing at the deleted rows unless `ondelete="CASCADE"` is set on those FKs.
  In our model only `CommandRequest.target_device_id` has CASCADE, so deleting
  a Device does NOT cascade to its `source_device_id` references.
- `Query.delete()` with `synchronize_session=False` is needed when deleting
  rows that may have stale ORM identity-map state from a different session
  (e.g. the long-lived `session` from `get_session()` passed into
  `create_backup_tarball`).

## Backup data structure
```python
{
    "ctrl_devices": [
        {"id", "display_name", "bearer_token", "ws_state", "last_seen",
         "extra", "registered_at", "is_first_webui_device"},
        ...
    ],
    "ctrl_device_acls": [
        {"id", "source_device", "target_device", "operation", "extra",
         "created_at"},
        ...
    ],
    "ctrl_bootstrap_tokens": [
        {"id", "device_id", "display_name", "expires_at", "consumed_at",
         "created_at"},
        ...
    ],
    "ctrl_operation_specs": [
        {"provider", "id", "group", "name", "description", "params_schema",
         "result_schema", "ui_hint", "registered_at", "last_seen"},
        ...
    ],
    "ctrl_command_requests": [
        {"id", "target_device_id", "source_device_id", "operation", "params",
         "status", "created_at", "claimed_at", "completed_at", "result",
         "error", "claim_token", "timeout_seconds"},
        ...
    ],
}
```

## Test result
```
ALL CONTROL PLANE BACKUP TESTS PASSED
```
