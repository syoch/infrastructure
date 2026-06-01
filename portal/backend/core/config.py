import os
import sys
import json

# Base Directories
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CORE_DIR)
PORTAL_DIR = os.path.dirname(BACKEND_DIR)
ROOT_DIR = os.path.dirname(PORTAL_DIR)

# Service Config (defaults, can be overridden by config JSON)
DEFAULT_PORT = 8000
HOST = "0.0.0.0"
DATABASE_URL = None
SQLITE_WAL = True
EXTENSIONS = [
    {"module": "servers.obtainium_repo", "class": "ObtainiumRepoExtension"}
]
STORAGE_PROVIDER = "StorageManagerExtension"

# Application Paths
PUBLIC_DIR = os.path.join(PORTAL_DIR, "public")

LOADED_EXTENSIONS = {}
EXTENSION_HOST = None
_config_dir = None

def get_config_dir() -> str:
    """Returns the directory containing the loaded config file, or ROOT_DIR if none loaded."""
    return _config_dir or ROOT_DIR

def resolve_config_path(path: str) -> str:
    """Resolves a path relative to the config file directory. Falls back to ROOT_DIR if not set."""
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(get_config_dir(), path))

def load_config(config_data: dict, config_dir: str = None):
    """Loads configuration dynamically from a dictionary, setting module-level variables."""
    global DEFAULT_PORT, HOST, DATABASE_URL, SQLITE_WAL, EXTENSIONS, PUBLIC_DIR, STORAGE_PROVIDER, _config_dir
    
    _config_dir = config_dir
    
    server_cfg = config_data.get("server", {})
    DEFAULT_PORT = server_cfg.get("port", DEFAULT_PORT)
    HOST = server_cfg.get("host", HOST)
    STORAGE_PROVIDER = server_cfg.get("storage_provider", STORAGE_PROVIDER)
    
    db_cfg = config_data.get("database", {})
    DATABASE_URL = db_cfg.get("url")
    if DATABASE_URL and DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL[len("sqlite:///"):]
        if db_path and not os.path.isabs(db_path):
            if config_dir:
                abs_db_path = os.path.abspath(os.path.join(config_dir, db_path))
                DATABASE_URL = f"sqlite:///{abs_db_path}"
                
    SQLITE_WAL = db_cfg.get("sqlite_wal", True)
    EXTENSIONS = config_data.get("extensions", EXTENSIONS)
    
    paths_cfg = config_data.get("paths", {})
    if "public_dir" in paths_cfg:
        PUBLIC_DIR = os.path.abspath(paths_cfg["public_dir"])

def load_config_from_file(config_path: str):
    """Helper to read JSON file and load configuration."""
    if not config_path:
        return
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at '{config_path}'")
        
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    config_dir = os.path.dirname(os.path.abspath(config_path))
    load_config(data, config_dir=config_dir)
