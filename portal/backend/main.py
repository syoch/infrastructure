#!/usr/bin/env python3
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

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Portal Server Backend")
    parser.add_argument("--config", help="Path to config JSON file")
    args, _ = parser.parse_known_args()
    if args.config:
        config.load_config_from_file(args.config)

    print("=" * 60)
    print("         Android Device Provisioning Portal")
    print("=" * 60)
    
    # Initialize Core Server
    server = PortalServer(host=config.HOST, port=config.DEFAULT_PORT)
    
    # Initialize Extensions dynamically
    extensions = load_extensions(config)
    
    # Initialize Database (Extensions must be loaded first so their models register onto Base.metadata)
    from backend.core.database import init_db
    print("Initializing database...")
    init_db()
    
    # Setup and register extensions
    for ext in extensions:
        print(f"Loading extension: {ext.__class__.__name__}...")
        ext.setup()
        server.register_extension(ext)
        
    print("-" * 60)
    print("Available Portal Access URLs:")
    local_ip = get_local_ip()
    print(f"  Local Portal UI:  http://{local_ip}:{config.DEFAULT_PORT}/")
    for ext in extensions:
        if hasattr(ext, "get_startup_info"):
            for line in ext.get_startup_info(local_ip):
                print(f"  {line}")
    print("=" * 60)

    server.start()

if __name__ == '__main__':
    main()
