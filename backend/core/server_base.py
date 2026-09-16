import logging
import os
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.core import config
from backend.core.api_backup import require_admin_device, router as backup_router

logger = logging.getLogger(__name__)

__all__ = ["PortalServer", "require_admin_device"]


class PortalServer:
    """
    Wrapper around FastAPI that aggregates routers from various extensions.
    """

    def __init__(self, host: str = config.HOST, port: int = config.DEFAULT_PORT):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Android Device Provisioning Portal")
        self.app.include_router(backup_router)

    def register_extension(self, extension: Any) -> None:
        """Mounts the extension router onto the main FastAPI application if present."""
        router = getattr(extension, "router", None)
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
            self.app.mount("/", StaticFiles(directory=config.PUBLIC_DIR, html=True), name="static")
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
