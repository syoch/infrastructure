"""Backup / restore API routes.

These are core (non-extension) routes, always mounted by PortalServer. Both
endpoints require a control-plane admin device (Bearer token).
"""
import logging
import os
import tempfile
import time
from typing import Any, Optional, TypedDict, cast

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core import config
from backend.core.auth import get_admin_device_dependency
from backend.core.database import get_db
from backend.core.protocols import StorageProvider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backup"])


class StatusMessageResponse(TypedDict):
    status: str
    message: str


class StatusMessageOut(BaseModel):
    status: str
    message: str


def require_admin_device(
    authorization: str = Header(default=""),
    token: str = Query(default=""),
    db: Session = Depends(get_db),
) -> Any:
    """Requires a control-plane admin device (Bearer token + is_first_webui_device).

    The provider is registered by the control-plane extension at startup; core
    does not import it directly. Without the extension loaded this returns 503.
    """
    provider = get_admin_device_dependency()
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="admin device auth requires the control-plane extension",
        )
    return provider(authorization=authorization, token=token, db=db)


def _storage_extension() -> Optional[StorageProvider]:
    host = config.EXTENSION_HOST
    if host is None:
        return None
    return cast(StorageProvider, host.get_extension(tags=["storage-provider"]))


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


@router.get("/api/backup")
def handle_backup(
    include_apks: bool = True,
    db: Session = Depends(get_db),
    _admin: Any = Depends(require_admin_device),
) -> Any:
    from backend.core.backup_manager import BackupManager

    try:
        storage_ext = _storage_extension()

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
        tmp_path = tmp_file.name
        tmp_file.close()

        BackupManager.create_backup_tarball(
            out_path=tmp_path,
            session=db,
            storage_ext=storage_ext,
            include_apks=include_apks,
        )

        filename = f"portal_backup_{int(time.time())}.tar.gz"
        background_tasks = BackgroundTasks()
        background_tasks.add_task(_remove_quietly, tmp_path)

        return FileResponse(
            path=tmp_path,
            filename=filename,
            media_type="application/gzip",
            background=background_tasks,
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - surface the failure to the client
        logger.exception("Backup failed")
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.post("/api/restore", response_model=StatusMessageOut)
async def handle_restore(
    file: UploadFile = File(...),
    strategy: str = Form("overwrite"),
    db: Session = Depends(get_db),
    _admin: Any = Depends(require_admin_device),
) -> StatusMessageResponse:
    if strategy not in ("overwrite", "merge"):
        raise HTTPException(
            status_code=400, detail="Invalid restore strategy. Must be 'overwrite' or 'merge'."
        )

    from backend.core.backup_manager import BackupManager

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
    tmp_path = tmp_file.name
    try:
        storage_ext = _storage_extension()
        try:
            content = await file.read()
            tmp_file.write(content)
        finally:
            tmp_file.close()

        BackupManager.restore_backup_tarball(
            in_path=tmp_path,
            session=db,
            storage_ext=storage_ext,
            strategy=strategy,
        )
        return {"status": "success", "message": "Server restoration completed successfully."}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - surface the failure to the client
        logger.exception("Restoration failed")
        raise HTTPException(status_code=500, detail=f"Restoration failed: {str(e)}")
    finally:
        _remove_quietly(tmp_path)
