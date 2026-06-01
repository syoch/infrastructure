#!/usr/bin/env python3
import os
import sys
import argparse

# Ensure portal root is in Python Path
PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))
if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

from backend.core import config
from backend.core.extension_loader import load_extensions

def main():
    parser = argparse.ArgumentParser(description="Portal Management Utility")
    parser.add_argument("--config", help="Path to config JSON file")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Management command")

    # Core commands
    backup_parser = subparsers.add_parser("backup", help="Create a server backup package")
    backup_parser.add_argument("--out", required=True, help="Output backup tarball filepath")
    backup_parser.add_argument("--no-apks", action="store_true", help="Do not bundle physical APK files in the backup")

    restore_parser = subparsers.add_parser("restore", help="Restore server from a backup package")
    restore_parser.add_argument("--in", required=True, dest="in_file", help="Input backup tarball filepath")
    restore_parser.add_argument("--strategy", choices=["overwrite", "merge"], default="overwrite", help="Conflict resolution strategy")

    # Pre-parse --config argument to load configuration before loading extensions
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", help="Path to config JSON file")
    pre_args, _ = pre_parser.parse_known_args()
    if pre_args.config:
        config.load_config_from_file(pre_args.config)

    # Initialize extensions dynamically for CLI registration
    extensions = load_extensions(config)

    for ext in extensions:
        ext.setup()
        ext.register_cli_commands(subparsers)

    # Global parsing
    args = parser.parse_args()

    if args.command == "backup":
        from backend.core.database import session_scope
        from backend.core.backup_manager import BackupManager
        host = getattr(config, "EXTENSION_HOST", None)
        storage_ext = host.get_extension(tags=["storage-provider"]) if host else None
        
        with session_scope() as session:
            BackupManager.create_backup_tarball(
                out_path=args.out,
                session=session,
                storage_ext=storage_ext,
                include_apks=not args.no_apks
            )

    elif args.command == "restore":
        from backend.core.database import session_scope
        from backend.core.backup_manager import BackupManager
        host = getattr(config, "EXTENSION_HOST", None)
        storage_ext = host.get_extension(tags=["storage-provider"]) if host else None
        
        with session_scope() as session:
            BackupManager.restore_backup_tarball(
                in_path=args.in_file,
                session=session,
                storage_ext=storage_ext,
                strategy=args.strategy
            )

    # Execution dispatch
    elif hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
