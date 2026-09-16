from datetime import datetime
from typing import Optional


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)
