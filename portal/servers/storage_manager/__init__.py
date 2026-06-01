import os
import hashlib
import time
import shutil
from fastapi import APIRouter, File, UploadFile, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from backend.extensions.base import BaseExtension
from backend.core.database import session_scope

class StorageManagerExtension(BaseExtension):
    """
    Plugin extension that provides generic RESTful Content-Addressable Storage (CAS) file management.
    """
    def __init__(self, core_config, ext_config=None):
        super().__init__(core_config)
        self.ext_config = ext_config or {}
        self.tags = ["storage-provider"]
        
        # Resolve uploads directory path.
        uploads_dir = self.ext_config.get("uploads_dir")
        if uploads_dir:
            from backend.core.config import resolve_config_path
            self.uploads_dir = resolve_config_path(uploads_dir)
        else:
            self.uploads_dir = os.path.join(self.config.PORTAL_DIR, "uploads")
            
        print(f"StorageManager initialized with uploads_dir: {self.uploads_dir}")
        self.router = APIRouter()
        self.setup_routes()

    def setup(self):
        # Ensure uploads directory exists
        os.makedirs(self.uploads_dir, exist_ok=True)

    def save_file(self, file_content: bytes) -> str:
        """Computes SHA-256 and saves file. Returns the file hash."""
        file_hash = hashlib.sha256(file_content).hexdigest()
        filepath = self.get_file_path(file_hash)
        with open(filepath, "wb") as f:
            f.write(file_content)
        return file_hash

    def _collect_referenced_hashes(self, session) -> set:
        """Dynamically gathers all referenced file hashes from loaded extensions."""
        referenced = set()
        if self.host:
            for ext in self.host._extensions.values():
                try:
                    ref_set = ext.get_referenced_file_hashes(session)
                    if ref_set:
                        referenced.update(ref_set)
                except Exception as e:
                    print(f"Warning: Failed to gather referenced hashes from '{ext.__class__.__name__}': {e}")
        return referenced

    def delete_file(self, file_hash: str) -> bool:
        """Physically removes the file if no references remain in any extension's models."""
        try:
            with session_scope() as session:
                referenced = self._collect_referenced_hashes(session)
                if file_hash not in referenced:
                    filepath = self.get_file_path(file_hash)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        print(f"Physically deleted orphan CAS file: {filepath}")
                        return True
            return False
        except Exception as e:
            print(f"Error during physical CAS deletion check: {e}")
            return False

    def garbage_collect(self) -> list:
        """Physically removes all files in CAS directory that are not referenced in the database, with 1h grace period."""
        try:
            with session_scope() as session:
                referenced_hashes = self._collect_referenced_hashes(session)
                deleted_hashes = []
                
                if os.path.exists(self.uploads_dir):
                    for filename in os.listdir(self.uploads_dir):
                        if filename.endswith(".apk"):
                            file_hash = filename[:-4]
                            if file_hash not in referenced_hashes:
                                filepath = os.path.join(self.uploads_dir, filename)
                                try:
                                    # Enforce 1 hour grace period
                                    mtime = os.path.getmtime(filepath)
                                    if time.time() - mtime > 3600:
                                        os.remove(filepath)
                                        print(f"GC deleted orphan CAS file: {filepath}")
                                        deleted_hashes.append(file_hash)
                                    else:
                                        print(f"GC skipped young orphan file: {filepath}")
                                except Exception as e:
                                    print(f"Error deleting file {filepath} during GC: {e}")
            return deleted_hashes
        except Exception as e:
            print(f"Error executing garbage collection: {e}")
            return []


    def get_file_path(self, file_hash: str) -> str:
        """Returns the absolute path to the file on disk matching the hash."""
        return os.path.join(self.uploads_dir, f"{file_hash}.apk")

    def setup_routes(self):
        @self.router.get("/api/storage/files")
        def serve_files_list():
            """GET /api/storage/files - Lists all stored files in CAS with their size."""
            files = []
            if os.path.exists(self.uploads_dir):
                for filename in os.listdir(self.uploads_dir):
                    if filename.endswith(".apk"):
                        file_hash = filename[:-4]
                        filepath = os.path.join(self.uploads_dir, filename)
                        try:
                            size = os.path.getsize(filepath)
                            files.append({"id": file_hash, "size": size})
                        except Exception:
                            pass
            return files

        @self.router.post("/api/storage/files")
        async def handle_upload(file: UploadFile = File(...)):
            """POST /api/storage/files - Uploads a file, hashes it, and saves it in CAS."""
            try:
                file_content = await file.read()
                if not file_content:
                    raise HTTPException(status_code=400, detail="Uploaded file is empty.")
                
                file_hash = self.save_file(file_content)
                return {
                    "status": "success",
                    "message": "File uploaded and saved in storage.",
                    "file_hash": file_hash
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

        @self.router.get("/api/storage/files/{file_hash}")
        def serve_download(file_hash: str, filename: str = Query(None)):
            """GET /api/storage/files/[file_hash] - Streams a file with dynamic friendly filename."""
            filepath = self.get_file_path(file_hash)
            if not os.path.exists(filepath):
                raise HTTPException(status_code=404, detail=f"File {file_hash} not found in storage")

            # Determine response filename
            if not filename:
                filename = f"{file_hash}.apk"

            return FileResponse(
                path=filepath,
                media_type="application/vnd.android.package-archive",
                filename=filename
            )

        @self.router.delete("/api/storage/files/{file_hash}")
        def handle_delete(file_hash: str):
            """DELETE /api/storage/files/[file_hash] - Physically deletes the file if unreferenced."""
            filepath = self.get_file_path(file_hash)
            if not os.path.exists(filepath):
                raise HTTPException(status_code=404, detail="File not found")

            deleted = self.delete_file(file_hash)
            if deleted:
                return {"status": "success", "message": "File deleted physically from storage."}
            else:
                return {"status": "skipped", "message": "Physical file delete skipped (referenced in database)."}

    def get_backup_directories(self) -> dict:
        """Returns the uploads directory to package in the backup tarball."""
        return {"uploads": self.uploads_dir}

    def restore_directories(self, temp_dir: str):
        """Restores physical CAS assets non-destructively from the temporary directory."""
        uploads_tmp_dir = os.path.join(temp_dir, "uploads")
        if os.path.exists(uploads_tmp_dir):
            os.makedirs(self.uploads_dir, exist_ok=True)
            for filename in os.listdir(uploads_tmp_dir):
                if filename.endswith(".apk"):
                    src_file = os.path.join(uploads_tmp_dir, filename)
                    dest_file = os.path.join(self.uploads_dir, filename)
                    # Content-addressable storage: copy only if it doesn't already exist
                    if not os.path.exists(dest_file):
                        shutil.copy2(src_file, dest_file)
                        print(f"Restored asset file: {filename}")

