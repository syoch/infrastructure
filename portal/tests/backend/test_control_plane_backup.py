#!/usr/bin/env python3
"""
Round-trip tests for the Control Plane extension's backup_data() and restore_data().

Verifies that:
1. backup_data() captures all 5 ctrl_* tables
2. restore_data(overwrite) drops existing rows and re-inserts from backup
3. restore_data(merge) keeps existing rows untouched and adds new ones
"""
import os
import sys
import json
import uuid
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(SCRIPT_DIR)
PORTAL_DIR = os.path.dirname(TESTS_DIR)
ROOT_DIR = os.path.dirname(PORTAL_DIR)

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

CONFIG_PATH = os.path.join(PORTAL_DIR, "tests", "config.test.json")
TEST_DB_PATH = os.path.join(PORTAL_DIR, "tests", "portal_test.db")

from backend.core import config
config.load_config_from_file(CONFIG_PATH)

from backend.core.database import get_session, session_scope
from backend.core.extension_loader import load_extensions
from backend.core.backup_manager import BackupManager
from servers.control_plane.models import (
    Device, DeviceACL, DeviceBootstrapToken, OperationSpec, CommandRequest,
)


def _bootstrap():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    if os.path.exists(TEST_DB_PATH + "-shm"):
        os.remove(TEST_DB_PATH + "-shm")
    if os.path.exists(TEST_DB_PATH + "-wal"):
        os.remove(TEST_DB_PATH + "-wal")
    extensions = load_extensions(config)
    for ext in extensions:
        ext.setup()
    from backend.core.database import init_db
    init_db()


def _seed():
    """Populate all 5 tables with known data."""
    with session_scope() as s:
        s.add(Device(
            id="webui",
            display_name="WebUI (source)",
            bearer_token="tk_webui_token",
            ws_state="online",
            is_first_webui_device=True,
        ))
        s.flush()
        s.add(Device(
            id="bkp-device-1",
            display_name="Backup Device 1",
            bearer_token="tk_bkp_token_1",
            ws_state="online",
            is_first_webui_device=False,
        ))
        s.flush()
        s.add(DeviceACL(
            id=str(uuid.uuid4()),
            source_device="device:.*",
            target_device="device:bkp-device-1",
            operation="device.reboot",
            extra="some meta",
        ))
        s.add(DeviceBootstrapToken(
            id=str(uuid.uuid4()),
            device_id="bkp-device-1",
            display_name="Bkp Token 1",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        ))
        s.add(OperationSpec(
            provider="device:bkp-device-1",
            id="device.reboot",
            group="device",
            name="device.reboot",
            description="Reboot the device",
            params_schema={"type": "object", "properties": {"delay": {"type": "integer"}}},
            ui_hint={"kind": "button", "label": "Reboot"},
        ))
        s.flush()
        s.add(CommandRequest(
            id=str(uuid.uuid4()),
            target_device_id="bkp-device-1",
            source_device_id="webui",
            operation="device.reboot",
            params={"delay": 5},
            status="pending",
            timeout_seconds=60,
            claim_token="ct_seed_token",
        ))


def _count_all(session):
    return {
        "devices": session.query(Device).count(),
        "acls": session.query(DeviceACL).count(),
        "tokens": session.query(DeviceBootstrapToken).count(),
        "ops": session.query(OperationSpec).count(),
        "commands": session.query(CommandRequest).count(),
    }


def _find_cpext():
    for ext_name, ext in config.LOADED_EXTENSIONS.items():
        if ext_name == "ControlPlaneExtension":
            return ext
    raise RuntimeError("ControlPlaneExtension not loaded")


def test_backup_captures_all_tables():
    print("=" * 60)
    print("Control Plane Backup/Restore Tests")
    print("=" * 60)
    print()
    print("[seed] populate 5 tables with known data...")
    _bootstrap()
    _seed()
    ext = _find_cpext()
    with session_scope() as s:
        backup = ext.backup_data(s)
        for k in ("ctrl_devices", "ctrl_device_acls", "ctrl_bootstrap_tokens",
                  "ctrl_operation_specs", "ctrl_command_requests"):
            assert k in backup, f"backup missing key: {k}"
        assert len(backup["ctrl_devices"]) == 2, f"expected 2 devices, got {len(backup['ctrl_devices'])}"
        assert len(backup["ctrl_device_acls"]) == 1, f"expected 1 acl, got {len(backup['ctrl_device_acls'])}"
        assert len(backup["ctrl_bootstrap_tokens"]) == 1, f"expected 1 token, got {len(backup['ctrl_bootstrap_tokens'])}"
        assert len(backup["ctrl_operation_specs"]) == 1, f"expected 1 op, got {len(backup['ctrl_operation_specs'])}"
        assert len(backup["ctrl_command_requests"]) == 1, f"expected 1 cmd, got {len(backup['ctrl_command_requests'])}"
    print("  -> backup captured all 5 tables (2 devices, 1 acl, 1 token, 1 op, 1 command)")


def test_backup_restore_via_tarball():
    print()
    print("[test] backup -> mutate -> restore (overwrite) via tarball")
    ext = _find_cpext()
    session = get_session()

    backup_file = os.path.join(SCRIPT_DIR, "test_cpext_backup.tar.gz")
    if os.path.exists(backup_file):
        os.remove(backup_file)

    BackupManager.create_backup_tarball(
        out_path=backup_file, session=session,
        storage_ext=config.LOADED_EXTENSIONS.get("StorageManagerExtension"),
        include_apks=False,
    )
    assert os.path.exists(backup_file), "backup tarball not created"
    print("  -> tarball created")

    with session_scope() as s:
        s.query(CommandRequest).delete()
        s.query(OperationSpec).delete()
        s.query(DeviceBootstrapToken).delete()
        s.query(DeviceACL).delete()
        s.query(Device).filter(Device.id.in_(["bkp-device-1", "webui"])).delete(synchronize_session=False)

    with session_scope() as s:
        counts_after_delete = _count_all(s)
    assert all(v == 0 for v in counts_after_delete.values()), f"delete incomplete: {counts_after_delete}"
    print("  -> all 5 tables cleared")

    BackupManager.restore_backup_tarball(
        in_path=backup_file, session=session,
        storage_ext=config.LOADED_EXTENSIONS.get("StorageManagerExtension"),
        strategy="overwrite",
    )

    with session_scope() as s:
        counts_after_restore = _count_all(s)
        d = s.query(Device).filter_by(id="bkp-device-1").first()
        assert d is not None, "device not restored"
        assert d.display_name == "Backup Device 1"
        assert d.bearer_token == "tk_bkp_token_1"
        assert d.is_first_webui_device is False
        assert d.ws_state == "online"
        ops = s.query(OperationSpec).filter_by(provider="device:bkp-device-1", id="device.reboot").first()
        assert ops is not None
        assert ops.ui_hint == {"kind": "button", "label": "Reboot"}
        cmds = s.query(CommandRequest).filter_by(target_device_id="bkp-device-1").first()
        assert cmds is not None
        assert cmds.status == "pending"
        assert cmds.claim_token == "ct_seed_token"
    assert counts_after_restore == {
        "devices": 2, "acls": 1, "tokens": 1, "ops": 1, "commands": 1,
    }, f"counts after restore: {counts_after_restore}"
    print(f"  -> restore via tarball verified: {counts_after_restore}")

    if os.path.exists(backup_file):
        os.remove(backup_file)


def test_backup_merge_preserves_existing():
    print()
    print("[test] merge strategy keeps existing rows + adds new ones")
    ext = _find_cpext()
    session = get_session()

    backup_file = os.path.join(SCRIPT_DIR, "test_cpext_merge_backup.tar.gz")
    if os.path.exists(backup_file):
        os.remove(backup_file)

    BackupManager.create_backup_tarball(
        out_path=backup_file, session=session,
        storage_ext=config.LOADED_EXTENSIONS.get("StorageManagerExtension"),
        include_apks=False,
    )
    print("  -> backup A created (contains: webui + bkp-device-1 + 1 ACL + 1 token + 1 op + 1 command)")

    with session_scope() as s:
        s.add(Device(
            id="extra-device",
            display_name="Extra Device (added AFTER backup A)",
            bearer_token="tk_extra_token",
            ws_state="offline",
            is_first_webui_device=False,
        ))
        s.add(DeviceACL(
            id=str(uuid.uuid4()),
            source_device="device:webui",
            target_device="device:extra-device",
            operation="device.reboot",
            extra="",
        ))

    with session_scope() as s:
        s.query(Device).filter_by(id="bkp-device-1").delete()
        s.query(OperationSpec).filter_by(provider="device:bkp-device-1").delete()
        s.query(DeviceBootstrapToken).filter_by(device_id="bkp-device-1").delete()
        s.query(CommandRequest).delete()
    print("  -> post-backup changes: added extra-device + removed bkp-device-1")

    with session_scope() as s:
        before = [(d.id, d.display_name) for d in s.query(Device).all()]
        acls_before = s.query(DeviceACL).count()
        assert len(before) == 2, f"expected 2 devices pre-restore, got {before}"
        assert acls_before == 2, f"expected 2 acls pre-restore, got {acls_before}"

    BackupManager.restore_backup_tarball(
        in_path=backup_file, session=session,
        storage_ext=config.LOADED_EXTENSIONS.get("StorageManagerExtension"),
        strategy="merge",
    )

    with session_scope() as s:
        d_bkp = s.query(Device).filter_by(id="bkp-device-1").first()
        d_extra = s.query(Device).filter_by(id="extra-device").first()
        d_webui = s.query(Device).filter_by(id="webui").first()
        assert d_bkp is not None, "bkp-device-1 missing after merge (should be re-added from backup)"
        assert d_extra is not None, "extra-device dropped by merge (should be kept)"
        assert d_webui is not None
        ops_bkp = s.query(OperationSpec).filter_by(provider="device:bkp-device-1").first()
        assert ops_bkp is not None, "backed-up op missing after merge"
        token_bkp = s.query(DeviceBootstrapToken).filter_by(device_id="bkp-device-1").first()
        assert token_bkp is not None
        cmd_bkp = s.query(CommandRequest).filter_by(target_device_id="bkp-device-1").first()
        assert cmd_bkp is not None
        acls = s.query(DeviceACL).count()
        assert acls == 2, f"expected 2 ACLs (1 from backup + 1 extra), got {acls}"
    print("  -> merge re-added backed-up bkp-device-1 + ACL + op + token + command")
    print("  -> merge preserved post-backup extra-device + its ACL")

    if os.path.exists(backup_file):
        os.remove(backup_file)


def main():
    try:
        test_backup_captures_all_tables()
        test_backup_restore_via_tarball()
        test_backup_merge_preserves_existing()
    except AssertionError as e:
        print(f"  !! FAILED: {e}")
        return 1
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 1
    print()
    print("=" * 60)
    print("      ALL CONTROL PLANE BACKUP TESTS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
