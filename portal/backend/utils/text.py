import re
import uuid


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or uuid.uuid4().hex[:12]


def strip_type_prefix(value: str) -> str:
    if ":" in value:
        _, pattern = value.split(":", 1)
        return pattern
    return value


def safe_app_name(app_name: str) -> str:
    safe = "".join(c for c in app_name if c.isalnum() or c in (" ", "_", "-")).strip()
    return safe.replace(" ", "_")
