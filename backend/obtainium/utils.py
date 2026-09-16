import re
from typing import Optional

from fastapi import Request
from backend.utils.network import get_local_ip
from backend.utils.text import safe_app_name


def export_apk_filename(app_name: str, app_id: str, version: str, architecture: Optional[str] = None) -> str:
    arch = f"_{architecture}" if architecture else ""
    return f"{safe_app_name(app_name)}_{app_id}_v{version}{arch}.apk"


def version_sort_key(version: str) -> list:
    parts = re.split(r"[._\-+]+", version or "")
    return [(int(p), "") if p.isdigit() else (0, p) for p in parts]


def select_latest_apk(apks: list):
    return max(apks, key=lambda a: (version_sort_key(a.version), a.id))

def get_base_url(request: Request, default_port: int = 8000) -> str:
    """
    Determines the public-facing base URL of the application.
    Prioritizes proxy headers to handle reverse proxies (like Nginx, Cloudflare).
    """
    host_header = request.headers.get('X-Forwarded-Host') or request.headers.get('Host')
    
    # Determine the scheme. Check X-Forwarded-Proto, then fall back to Cloudflare's cf-visitor.
    proto_header = request.headers.get('X-Forwarded-Proto', '').lower()
    cf_visitor = request.headers.get('cf-visitor', '')
    cf_uses_https = '"scheme":"https"' in cf_visitor
    
    if proto_header == 'https' or (proto_header == 'http' and cf_uses_https):
        scheme = 'https'
    elif proto_header == 'http':
        scheme = 'http'
    elif cf_uses_https:
        scheme = 'https'
    else:
        scheme = 'https' if request.url.scheme == 'https' else 'http'
        
    if host_header:
        return f"{scheme}://{host_header}"
        
    return f"http://{get_local_ip()}:{default_port}"
