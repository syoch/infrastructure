#!/usr/bin/env python3
import logging
import os
import sys

# Ensure portal root is in Python Path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.dirname(BACKEND_DIR)
if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

from backend.core import config
from backend.core.server_base import PortalServer
from backend.utils.network import get_local_ip

# Import Extensions Loader
from backend.core.extension_loader import load_extensions

logger = logging.getLogger("portal")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Portal Server Backend")
    parser.add_argument("--config", help="Path to config JSON file")
    parser.add_argument("--log-level", default=os.environ.get("PORTAL_LOG_LEVEL", "INFO"))
    args, _ = parser.parse_known_args()
    if args.config:
        config.load_config_from_file(args.config)

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("Android Device Provisioning Portal starting")

    # Initialize Core Server
    server = PortalServer(host=config.HOST, port=config.DEFAULT_PORT)

    # Initialize Extensions dynamically
    extensions = load_extensions(config)

    # Initialize Database (Extensions must be loaded first so their models register onto Base.metadata)
    from backend.core.database import init_db

    logger.info("Initializing database...")
    init_db()

    # Setup and register extensions
    for ext in extensions:
        logger.info("Loading extension: %s...", ext.__class__.__name__)
        ext.setup()
        server.register_extension(ext)
        ext.install_event_loop_capture(server.app)

    local_ip = get_local_ip()
    logger.info("Available Portal Access URLs:")
    logger.info("  Local Portal UI:  http://%s:%s/", local_ip, config.DEFAULT_PORT)
    for ext in extensions:
        for line in ext.get_startup_info(local_ip):
            logger.info("  %s", line)

    server.start()


if __name__ == "__main__":
    main()
