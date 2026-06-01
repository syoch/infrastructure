#!/usr/bin/env python3
import os
import sys
import json
import shutil

# Ensure portal root is in Python Path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(SCRIPT_DIR)
PORTAL_DIR = os.path.dirname(TESTS_DIR)
ROOT_DIR = os.path.dirname(PORTAL_DIR)

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

CONFIG_PATH = os.path.join(PORTAL_DIR, 'tests', 'config.test.json')
from backend.core import config
config.load_config_from_file(CONFIG_PATH)

from backend.core.database import get_session
from servers.obtainium_repo.models import App, Category, Setting, LocalAppAPK
from backend.core.backup_manager import BackupManager
from backend.core import config
from servers.storage_manager import StorageManagerExtension
from servers.obtainium_repo.compiler import ObtainiumConfigCompiler
from servers.obtainium_repo.manager_cli import ObtainiumRepoManagerCLI

def run_test():
    print("=" * 60)
    print("      Testing Backup and Restore Manager")
    print("=" * 60)

    # Initialize Extensions
    from backend.core.extension_loader import load_extensions
    extensions = load_extensions(config)
    for ext in extensions:
        ext.setup()

    storage_ext = config.LOADED_EXTENSIONS.get("StorageManagerExtension")
    obtainium_repo_ext = config.LOADED_EXTENSIONS.get("ObtainiumRepoExtension")

    session = get_session()

    # 1. Clean Database
    print("Cleaning database...")
    session.query(LocalAppAPK).delete()
    session.query(App).delete()
    session.query(Category).delete()
    session.query(Setting).delete()
    session.commit()

    # 2. Add Dummy Data
    print("Inserting dummy test data...")
    cat = Category(name="BackupCategory", color=4284857472)
    session.add(cat)

    app = App(
        id="com.backup.test",
        name="Backup Test App",
        url="https://github.com/dummy/backup-test",
        override_source="GitHub",
        preferred_apk_index=None,
        pinned=True,
        allow_id_change=False,
        additional_settings={"test_key": "test_val"}
    )
    session.add(app)
    app.categories.append(cat)

    app_html = App(
        id="com.backup.html",
        name="Self-Hosted HTML App",
        url="http://192.168.1.200:12345/scrape-index.html",
        override_source="HTML",
        preferred_apk_index=None,
        pinned=False,
        allow_id_change=False,
        additional_settings={}
    )
    session.add(app_html)

    setting = Setting(key="test_setting", value="test_value")
    session.add(setting)

    # Create dummy CAS asset file
    dummy_hash = "abc123hash"
    dummy_apk_path = storage_ext.get_file_path(dummy_hash)
    os.makedirs(os.path.dirname(dummy_apk_path), exist_ok=True)
    with open(dummy_apk_path, "w") as f:
        f.write("dummy apk data content")

    apk_record = LocalAppAPK(
        app_id="com.backup.test",
        version="1.0.0",
        architecture="arm64-v8a",
        file_hash=dummy_hash
    )
    session.add(apk_record)
    session.commit()

    print("Dummy data populated.")

    # 3. Perform Backup
    backup_file = os.path.join(SCRIPT_DIR, "test_backup.tar.gz")
    if os.path.exists(backup_file):
        os.remove(backup_file)

    print("Running backup creation...")
    BackupManager.create_backup_tarball(
        out_path=backup_file,
        session=session,
        storage_ext=storage_ext,
        include_apks=True
    )

    if not os.path.exists(backup_file):
        print("Error: Backup archive was not created.")
        sys.exit(1)
    print("Backup archive verified.")

    # 4. Modify data to simulate data changes/corruption
    print("Modifying database content to test restore...")
    # Change app url, delete setting
    app.url = "https://github.com/corrupted/url"
    session.query(Setting).filter_by(key="test_setting").delete()
    session.commit()

    # Physically delete the apk file
    if os.path.exists(dummy_apk_path):
        os.remove(dummy_apk_path)

    # 5. Run Restore (Overwrite)
    print("Running restore (Overwrite)...")
    BackupManager.restore_backup_tarball(
        in_path=backup_file,
        session=session,
        storage_ext=storage_ext,
        strategy="overwrite"
    )

    # Re-fetch records
    restored_app = session.query(App).filter_by(id="com.backup.test").first()
    restored_html_app = session.query(App).filter_by(id="com.backup.html").first()
    restored_setting = session.query(Setting).filter_by(key="test_setting").first()
    restored_apk_record = session.query(LocalAppAPK).filter_by(app_id="com.backup.test").first()

    # Assert database records
    if not restored_app or restored_app.url != "https://github.com/dummy/backup-test":
        print(f"Restore failed: app URL not reverted. URL is: {restored_app.url if restored_app else 'None'}")
        sys.exit(1)
    if not restored_html_app or restored_html_app.url != "/scrape-index.html":
        print(f"Restore failed: HTML app URL not sanitized. URL is: {restored_html_app.url if restored_html_app else 'None'}")
        sys.exit(1)
    if not restored_setting or restored_setting.value != "test_value":
        print("Restore failed: setting not restored.")
        sys.exit(1)
    if not restored_apk_record or restored_apk_record.file_hash != dummy_hash:
        print("Restore failed: LocalAppAPK record not restored.")
        sys.exit(1)

    # Assert physical assets
    if not os.path.exists(dummy_apk_path):
        print("Restore failed: physical APK file not restored.")
        sys.exit(1)

    print("Success: Overwrite restore validated successfully!")

    # 6. Test Restore (Merge)
    # Add new records manually, modify restored_app again
    print("Modifying data to test Merge strategy...")
    restored_app.url = "https://github.com/merged/url"
    
    new_cat = Category(name="MergeCategory", color=123)
    session.add(new_cat)
    session.commit()

    print("Running restore (Merge)...")
    BackupManager.restore_backup_tarball(
        in_path=backup_file,
        session=session,
        storage_ext=storage_ext,
        strategy="merge"
    )

    merged_app = session.query(App).filter_by(id="com.backup.test").first()
    merged_cat = session.query(Category).filter_by(name="MergeCategory").first()

    # Overwrite on App record from backup during merge
    if not merged_app or merged_app.url != "https://github.com/dummy/backup-test":
        print("Restore (Merge) failed: App URL was not synced back to backup state.")
        sys.exit(1)

    # Category added prior to restore should remain because of merge strategy
    if not merged_cat:
        print("Restore (Merge) failed: MergeCategory was deleted (should have been kept).")
        sys.exit(1)

    print("Success: Merge restore validated successfully!")

    # 7. Cleanup & Re-bootstrap database for E2E tests
    print("Cleaning up test artifacts...")
    if os.path.exists(backup_file):
        os.remove(backup_file)
    if os.path.exists(dummy_apk_path):
        os.remove(dummy_apk_path)

    print("Re-seeding database from seed_backup.tar.gz...")
    seed_backup_path = os.path.join(PORTAL_DIR, 'tests', 'bootstrap', 'seed_backup.tar.gz')
    BackupManager.restore_backup_tarball(
        in_path=seed_backup_path,
        session=session,
        storage_ext=storage_ext,
        strategy="overwrite"
    )

    session.close()
    print("=" * 60)
    print("          ALL BACKUP/RESTORE TESTS PASSED")
    print("=" * 60)

if __name__ == '__main__':
    run_test()
