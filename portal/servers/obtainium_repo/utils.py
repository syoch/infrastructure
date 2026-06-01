from fastapi import Request
from backend.utils.network import get_local_ip

def get_base_url(request: Request, default_port: int = 8000) -> str:
    """
    Determines the public-facing base URL of the application.
    Prioritizes proxy headers to handle reverse proxies (like Nginx, Cloudflare).
    """
    host_header = request.headers.get('X-Forwarded-Host') or request.headers.get('Host')
    
    # Determine the scheme. Check X-Forwarded-Proto, then fall back to Cloudflare's cf-visitor.
    proto_header = request.headers.get('X-Forwarded-Proto', '').lower()
    if proto_header in ('https', 'http'):
        scheme = proto_header
    else:
        cf_visitor = request.headers.get('cf-visitor', '')
        if '"scheme":"https"' in cf_visitor:
            scheme = 'https'
        else:
            scheme = 'https' if request.url.scheme == 'https' else 'http'
        
    if host_header:
        return f"{scheme}://{host_header}"
        
    return f"http://{get_local_ip()}:{default_port}"
