import os
import sys
import json
import shutil
import tarfile
import tempfile
import time
from backend.core.database import Base

class BackupManager:
    @staticmethod
    def _get_extensions():
        from backend.core import config
        host = getattr(config, "EXTENSION_HOST", None)
        if not host:
            return []
        # Return all loaded extension instances
        return list(host._extensions.values())

    @classmethod
    def serialize_db(cls, session) -> dict:
        """Serializes relational database records dynamically via extensions."""
        ext_data = {}
        for ext in cls._get_extensions():
            try:
                data = ext.backup_data(session)
                if data:
                    ext_data[ext.__class__.__name__] = data
            except Exception as e:
                print(f"Error during backup serialization for extension '{ext.__class__.__name__}': {e}")
        return {
            "extensions": ext_data
        }

    @classmethod
    def deserialize_db(cls, session, data: dict, strategy: str = "overwrite"):
        """Deserializes records dynamically by delegating to extensions."""
        if strategy == "overwrite":
            print("Wiping existing database records dynamically for fresh restoration...")
            # Reflect and delete all registered tables in Base metadata in dependency order
            # (reversed sorted_tables to drop/delete from dependent tables first)
            for table in reversed(Base.metadata.sorted_tables):
                try:
                    # SQLite does not support TRUNCATE, so we execute a DELETE
                    session.execute(table.delete())
                except Exception as table_err:
                    print(f"Warning: Failed to clear table '{table.name}': {table_err}")
            session.flush()

        extensions_data = data.get("extensions", {})
        for ext in cls._get_extensions():
            ext_name = ext.__class__.__name__
            if ext_name in extensions_data:
                try:
                    ext.restore_data(session, extensions_data[ext_name], strategy)
                except Exception as e:
                    print(f"Error restoring database data for extension '{ext_name}': {e}")
                    raise e
        session.flush()

    @classmethod
    def create_backup_tarball(cls, out_path: str, session, storage_ext=None, include_apks: bool = True):
        """Generates a compressed tarball containing database serialization and physical assets."""
        print(f"Starting backup. Export path: {out_path}")
        
        # Serialize database metadata
        db_data = cls.serialize_db(session)

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Write metadata file
            metadata_path = os.path.join(tmp_dir, "metadata.json")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(db_data, f, ensure_ascii=False, indent=2)

            # Write manifest file
            manifest_path = os.path.join(tmp_dir, "manifest.json")
            manifest = {
                "version": "2.0",  # Bumped to version 2.0 due to modular structure
                "timestamp": int(time.time() * 1000),
                "include_apks": include_apks
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            # Package physical directories if configured
            packed_dirs = []
            if include_apks:
                for ext in cls._get_extensions():
                    try:
                        dirs = ext.get_backup_directories()
                        for subfolder, local_path in dirs.items():
                            if os.path.exists(local_path):
                                dest_path = os.path.join(tmp_dir, subfolder)
                                os.makedirs(dest_path, exist_ok=True)
                                # Copy files over
                                for filename in os.listdir(local_path):
                                    src_file = os.path.join(local_path, filename)
                                    if os.path.isfile(src_file):
                                        shutil.copy2(src_file, os.path.join(dest_path, filename))
                                print(f"Bundled assets directory '{local_path}' into '{subfolder}'")
                                packed_dirs.append(subfolder)
                    except Exception as e:
                        print(f"Error backing up physical directories for extension '{ext.__class__.__name__}': {e}")

            # Write tarball
            with tarfile.open(out_path, "w:gz") as tar:
                tar.add(metadata_path, arcname="metadata.json")
                tar.add(manifest_path, arcname="manifest.json")
                for subfolder in packed_dirs:
                    tar.add(os.path.join(tmp_dir, subfolder), arcname=subfolder)
            
        print("Backup created successfully.")

    @classmethod
    def restore_backup_tarball(cls, in_path: str, session, storage_ext=None, strategy: str = "overwrite"):
        """Extracts and applies backup tarball content dynamically."""
        print(f"Starting restoration from: {in_path} using strategy: {strategy}")
        
        if not os.path.exists(in_path):
            raise FileNotFoundError(f"Backup file not found at: {in_path}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Extract tarball (safely: filter='data' on Python 3.12+,
            # manual path-traversal check on older versions)
            with tarfile.open(in_path, "r:gz") as tar:
                if sys.version_info >= (3, 12):
                    tar.extractall(path=tmp_dir, filter="data")
                else:
                    real_tmp = os.path.realpath(tmp_dir)
                    for member in tar.getmembers():
                        member_path = os.path.realpath(os.path.join(tmp_dir, member.name))
                        if not member_path.startswith(real_tmp + os.sep) and member_path != real_tmp:
                            raise ValueError(f"Path traversal attempt in tarball: {member.name}")
                    tar.extractall(path=tmp_dir)

            metadata_path = os.path.join(tmp_dir, "metadata.json")
            manifest_path = os.path.join(tmp_dir, "manifest.json")

            if not os.path.exists(metadata_path) or not os.path.exists(manifest_path):
                raise ValueError("Invalid backup structure: missing metadata or manifest.")

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            with open(metadata_path, "r", encoding="utf-8") as f:
                db_data = json.load(f)

            # 1. Restore Physical Assets by delegating to extensions (Non-destructively)
            for ext in cls._get_extensions():
                try:
                    ext.restore_directories(tmp_dir)
                except Exception as e:
                    print(f"Warning: Failed to restore directories for extension '{ext.__class__.__name__}': {e}")

            # 2. Restore Relational Database (Within a transaction)
            try:
                # Handle backwards compatibility for v1.0 backup metadata structure
                if "extensions" not in db_data:
                    print("Adapting v1.0 flat database backup to v2.0 modular format...")
                    # v1.0 structure was directly {"categories": ..., "apps": ..., "settings": ..., "local_app_apks": ...}
                    # We map this to the "ObtainiumRepoExtension" namespace
                    db_data = {
                        "extensions": {
                            "ObtainiumRepoExtension": db_data
                        }
                    }

                cls.deserialize_db(session, db_data, strategy=strategy)
                session.commit()
                print("Restoration database changes committed successfully.")
            except Exception as e:
                session.rollback()
                print(f"Restoration database changes rolled back due to error: {e}")
                raise e

            # 3. Trigger post-restore callback on extensions
            for ext in cls._get_extensions():
                try:
                    if hasattr(ext, "post_restore"):
                        ext.post_restore(strategy=strategy)
                except Exception as e:
                    print(f"Warning: post_restore hook failed for extension '{ext.__class__.__name__}': {e}")

        print("Restoration process finished.")
