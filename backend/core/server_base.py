import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from backend.core import config
from backend.extensions.base import BaseExtension
from backend.core.api_backup import require_admin_device, router as backup_router

logger = logging.getLogger(__name__)

__all__ = ["PortalServer", "require_admin_device"]


def _is_spa_path(path: str) -> bool:
    """True for client-side routes (no file extension, not an API call)."""
    if path.startswith("/api/"):
        return False
    last_segment = path.rstrip("/").rsplit("/", 1)[-1]
    return "." not in last_segment


class _SPAStaticFiles(StaticFiles):
    """StaticFiles that serves index.html for unknown client-side routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and _is_spa_path(str(scope.get("path", ""))):
                index = os.path.join(config.PUBLIC_DIR, "index.html")
                if os.path.exists(index):
                    return FileResponse(index)
            raise


class PortalServer:
    """
    Wrapper around FastAPI that aggregates routers from various extensions.
    """

    def __init__(self, host: str = config.HOST, port: int = config.DEFAULT_PORT):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Android Device Provisioning Portal")
        self.app.include_router(backup_router)

    def register_extension(self, extension: BaseExtension) -> None:
        """Mounts the extension router onto the main FastAPI application if present."""
        router = extension.router
        if router:
            self.app.include_router(router)
            logger.info("Mounted router for extension: %s", extension.__class__.__name__)
        else:
            logger.debug("No router defined for extension: %s", extension.__class__.__name__)

    def start(self) -> None:
        """Starts the FastAPI server using Uvicorn."""
        # Serve static files from config.PUBLIC_DIR at the root path "/"
        # Note: StaticFiles should be mounted AFTER API routes to avoid matching api calls as static files
        if os.path.exists(config.PUBLIC_DIR):
            self.app.mount(
                "/", _SPAStaticFiles(directory=config.PUBLIC_DIR, html=True), name="static"
            )
            logger.info("Mounted static files directory: %s", config.PUBLIC_DIR)
        else:
            logger.warning("Static files directory %s not found.", config.PUBLIC_DIR)

        logger.info("Portal server listening on http://%s:%s", self.host, self.port)

        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            proxy_headers=True,
            forwarded_allow_ips="127.0.0.1",
        )
