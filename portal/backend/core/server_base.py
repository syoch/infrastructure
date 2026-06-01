import os
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from backend.core import config
from backend.core.database import get_db

class PortalServer:
    """
    Wrapper around FastAPI that aggregates routers from various extensions.
    """
    def __init__(self, host=config.HOST, port=config.DEFAULT_PORT):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Android Device Provisioning Portal")
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.setup_backup_restore_routes()

    def register_extension(self, extension):
        """Mounts the extension router onto the main FastAPI application if present."""
        router = getattr(extension, "router", None)
        if router:
            self.app.include_router(router)
            print(f"Mounted router for extension: {extension.__class__.__name__}")
        else:
            print(f"No router defined for extension: {extension.__class__.__name__}")

    def start(self):
        """Starts the FastAPI server using Uvicorn."""
        # Serve static files from config.PUBLIC_DIR at the root path "/"
        # Note: StaticFiles should be mounted AFTER API routes to avoid matching api calls as static files
        if os.path.exists(config.PUBLIC_DIR):
            self.app.mount("/", StaticFiles(directory=config.PUBLIC_DIR, html=True), name="static")
            print(f"Mounted static files directory: {config.PUBLIC_DIR}")
        else:
            print(f"Warning: Static files directory {config.PUBLIC_DIR} not found.")

        print("-" * 60)
        print(f"Portal server listening on http://{self.host}:{self.port}")
        print("-" * 60)
        
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info", proxy_headers=True, forwarded_allow_ips="*")

    def setup_backup_restore_routes(self):
        from backend.core.backup_manager import BackupManager
        import tempfile
        import time

        @self.app.get("/api/backup")
        def handle_backup(include_apks: bool = True, db: Session = Depends(get_db)):
            try:
                storage_ext = getattr(config, "EXTENSION_HOST", None).get_extension(tags=["storage-provider"])
                
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
                tmp_path = tmp_file.name
                tmp_file.close()

                BackupManager.create_backup_tarball(
                    out_path=tmp_path,
                    session=db,
                    storage_ext=storage_ext,
                    include_apks=include_apks
                )

                filename = f"portal_backup_{int(time.time())}.tar.gz"
                
                background_tasks = BackgroundTasks()
                def remove_file(path: str):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                background_tasks.add_task(remove_file, tmp_path)

                return FileResponse(
                    path=tmp_path,
                    filename=filename,
                    media_type="application/gzip",
                    background=background_tasks
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

        @self.app.post("/api/restore")
        async def handle_restore(
            file: UploadFile = File(...),
            strategy: str = Form("overwrite"),
            db: Session = Depends(get_db)
        ):
            if strategy not in ("overwrite", "merge"):
                raise HTTPException(status_code=400, detail="Invalid restore strategy. Must be 'overwrite' or 'merge'.")
            
            try:
                storage_ext = getattr(config, "EXTENSION_HOST", None).get_extension(tags=["storage-provider"])
                
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
                tmp_path = tmp_file.name
                try:
                    content = await file.read()
                    tmp_file.write(content)
                finally:
                    tmp_file.close()



                BackupManager.restore_backup_tarball(
                    in_path=tmp_path,
                    session=db,
                    storage_ext=storage_ext,
                    strategy=strategy
                )
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

                return {"status": "success", "message": "Server restoration completed successfully."}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Restoration failed: {str(e)}")
