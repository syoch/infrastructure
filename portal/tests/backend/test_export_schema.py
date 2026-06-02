"""
Schema-validation test for the Obtainium export JSON.

The export is consumed by Obtainium's "Obtainium Import" feature, which calls
`App.fromJson` on each entry. That constructor expects exactly the 18 fields
defined in `App.toJson` (see Obtainium's source_provider.dart). This test
guarantees the portal's compiler emits a structurally compatible payload,
including a self-hosted (HTML-overridden) app entry.
"""

import os
import sys
import json
import time
import tempfile
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(SCRIPT_DIR)
PORTAL_DIR = os.path.dirname(TESTS_DIR)
ROOT_DIR = os.path.dirname(PORTAL_DIR)
BACKUP_DIR = os.path.join(TESTS_DIR, 'bootstrap')

if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

CONFIG_PATH = os.path.join(TESTS_DIR, 'config.test.json')
from backend.core import config
config.load_config_from_file(CONFIG_PATH)

from backend.core.database import session_scope, get_session
from backend.core.backup_manager import BackupManager
from servers.obtainium_repo.models import App, Category, Setting, LocalAppAPK
from servers.obtainium_repo.compiler import ObtainiumConfigCompiler

REQUIRED_APP_FIELDS = [
    'id', 'url', 'author', 'name', 'installedVersion', 'latestVersion',
    'apkUrls', 'otherAssetUrls', 'preferredApkIndex', 'additionalSettings',
    'lastUpdateCheck', 'pinned', 'categories', 'releaseDate', 'changeLog',
    'overrideSource', 'allowIdChange', 'pendingRepoRenameUrl',
]

def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def reset_db():
    session = get_session()
    session.query(LocalAppAPK).delete()
    session.query(App).delete()
    session.query(Category).delete()
    session.query(Setting).delete()
    session.commit()
    session.close()


def seed_apps():
    with session_scope() as session:
        cat = Category(name='TestCat', color=4284857472)
        session.add(cat)

        gh_app = App(
            id='test.gh.app',
            name='GH App',
            url='https://github.com/SomeOrg/SomeRepo',
            override_source='GitHub',
            preferred_apk_index=0,
            pinned=True,
            allow_id_change=False,
            additional_settings={'includePrereleases': False, 'versionDetection': True},
        )
        gh_app.categories = [cat]
        session.add(gh_app)

        sh_app = App(
            id='test.sh.app',
            name='SH App',
            url='placeholder',
            override_source=None,
            preferred_apk_index=0,
            pinned=False,
            allow_id_change=False,
            additional_settings={},
        )
        sh_app.categories = [cat]
        session.add(sh_app)
        session.flush()
        apk = LocalAppAPK(app_id=sh_app.id, file_hash='deadbeef', version='1.2.3', architecture='arm64-v8a')
        session.add(apk)


def validate_app(app):
    keys = set(app.keys())
    missing = set(REQUIRED_APP_FIELDS) - keys
    if missing:
        fail(f"App {app.get('id')} missing required fields: {missing}")

    # Top-level "version" must NOT be present
    extra = keys - set(REQUIRED_APP_FIELDS)
    non_internal = {e for e in extra if not e.startswith('_')}
    if non_internal:
        fail(f"App {app['id']} has unexpected non-internal fields: {non_internal}")

    # String fields
    for f in ['id', 'url', 'author', 'name', 'apkUrls', 'otherAssetUrls', 'additionalSettings']:
        if not isinstance(app[f], str):
            fail(f"App {app['id']} field {f} is {type(app[f]).__name__}, expected str")

    # JSON-encoded strings must be parseable
    for f in ['apkUrls', 'otherAssetUrls', 'additionalSettings']:
        try:
            json.loads(app[f])
        except Exception as e:
            fail(f"App {app['id']} field {f} is not valid JSON: {e}")

    # Integers
    if not isinstance(app['lastUpdateCheck'], int):
        fail(f"App {app['id']} lastUpdateCheck is {type(app['lastUpdateCheck']).__name__}, expected int")
    if not isinstance(app['preferredApkIndex'], int) and app['preferredApkIndex'] is not None:
        fail(f"App {app['id']} preferredApkIndex is {type(app['preferredApkIndex']).__name__}, expected int or null")

    # Booleans
    if not isinstance(app['pinned'], bool):
        fail(f"App {app['id']} pinned is {type(app['pinned']).__name__}, expected bool")
    if not isinstance(app['allowIdChange'], bool):
        fail(f"App {app['id']} allowIdChange is {type(app['allowIdChange']).__name__}, expected bool")

    # List
    if not isinstance(app['categories'], list):
        fail(f"App {app['id']} categories is {type(app['categories']).__name__}, expected list")

    # Nullable scalars
    for f in ['installedVersion', 'latestVersion', 'releaseDate', 'changeLog', 'overrideSource', 'pendingRepoRenameUrl']:
        # Anything (string, int, None) is acceptable for these as long as it's not undefined
        if f not in app:
            fail(f"App {app['id']} missing nullable field: {f}")


def run():
    reset_db()
    seed_apps()

    compiler = ObtainiumConfigCompiler(config)
    with session_scope() as session:
        out = compiler.compile_master('https://portal.example.test', session=session)

    # Top-level must not have a custom "version" key
    if 'version' in out:
        fail(f"Top-level contains a 'version' key: {out.get('version')!r}")

    if 'apps' not in out:
        fail("Top-level missing 'apps' key")
    if len(out['apps']) != 2:
        fail(f"Expected 2 apps, got {len(out['apps'])}")

    for app in out['apps']:
        validate_app(app)

    by_id = {a['id']: a for a in out['apps']}

    # GitHub app: author inferred from URL
    gh = by_id['test.gh.app']
    if gh['author'] != 'SomeOrg':
        fail(f"GitHub app author expected 'SomeOrg', got {gh['author']!r}")
    if gh['overrideSource'] != 'GitHub':
        fail(f"GitHub app overrideSource should be 'GitHub', got {gh['overrideSource']!r}")
    if gh['apkUrls'] != '[["placeholder", "placeholder"]]':
        fail(f"GitHub app apkUrls should be placeholder, got {gh['apkUrls']!r}")
    if not gh['pinned']:
        fail("GitHub app pinned should be True")

    # Self-hosted app: must be HTML-overridden with scrape-index URL
    sh = by_id['test.sh.app']
    if sh['overrideSource'] != 'HTML':
        fail(f"Self-hosted app overrideSource should be 'HTML', got {sh['overrideSource']!r}")
    if '/scrape-index.html' not in sh['url']:
        fail(f"Self-hosted app url should contain '/scrape-index.html', got {sh['url']!r}")

    apk_urls = json.loads(sh['apkUrls'])
    if not isinstance(apk_urls, list) or len(apk_urls) != 1 or len(apk_urls[0]) != 2:
        fail(f"Self-hosted app apkUrls malformed: {apk_urls!r}")
    name, url = apk_urls[0]
    if not name.endswith('.apk'):
        fail(f"Self-hosted APK name should end with .apk, got {name!r}")
    if '/api/apps/download/' not in url:
        fail(f"Self-hosted APK url should contain '/api/apps/download/', got {url!r}")
    if sh['latestVersion'] != '1.2.3':
        fail(f"Self-hosted app latestVersion should be '1.2.3', got {sh['latestVersion']!r}")

    # lastUpdateCheck should be very recent (within 1 hour of now)
    micros = sh['lastUpdateCheck']
    if abs(micros / 1_000_000 - time.time()) > 3600:
        fail(f"lastUpdateCheck should be within 1 hour of now, got {micros}")

    # Verify portal-internal underscore fields for self-hosted
    if sh.get('_version') != '1.2.3':
        fail(f"Self-hosted _version should be '1.2.3', got {sh.get('_version')!r}")
    if not isinstance(sh.get('_latest_apk_id'), int):
        fail(f"Self-hosted _latest_apk_id should be int, got {sh.get('_latest_apk_id')!r}")

    # Reseed DB for downstream tests
    print("Re-seeding database from seed_backup.tar.gz...")
    seed_backup_path = os.path.join(BACKUP_DIR, 'seed_backup.tar.gz')
    storage_ext = config.LOADED_EXTENSIONS.get("StorageManagerExtension")
    session = get_session()
    BackupManager.restore_backup_tarball(
        in_path=seed_backup_path,
        session=session,
        storage_ext=storage_ext,
        strategy="overwrite"
    )
    session.close()

    print("PASS: Obtainium export JSON is structurally compatible (all 18 fields, correct types, self-hosted handled).")


if __name__ == '__main__':
    run()
