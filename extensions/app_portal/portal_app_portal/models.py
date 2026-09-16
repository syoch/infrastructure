import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped
from backend.core.database import Base


def _uuid4() -> str:
    return str(uuid.uuid4())


class WebApp(Base):
    __tablename__ = "app_portal_web_apps"

    id: Mapped[str] = Column(String(36), primary_key=True, default=_uuid4)
    slug: Mapped[str] = Column(String(128), unique=True, nullable=False, index=True)
    name: Mapped[str] = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(1024), nullable=True)
    project_directory: Mapped[str] = Column(Text, nullable=False)
    opencode_session_id: Mapped[str] = Column(String(128), nullable=False)
    bridge_device_id: Mapped[str] = Column(String(64), nullable=False, index=True)
    source: Mapped[str] = Column(String(32), nullable=False, default="manual")
    tags: Mapped[list[str]] = Column(JSON, nullable=False, default=list)
    status: Mapped[str] = Column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<WebApp slug={self.slug!r} session={self.opencode_session_id!r}>"


class Feedback(Base):
    __tablename__ = "app_portal_feedback"

    id: Mapped[str] = Column(String(36), primary_key=True, default=_uuid4)
    app_id: Mapped[str] = Column(
        String(36),
        ForeignKey("app_portal_web_apps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author = Column(String(128), nullable=True)
    body: Mapped[str] = Column(Text, nullable=False)
    kind: Mapped[str] = Column(String(32), nullable=False, default="feedback")
    status: Mapped[str] = Column(String(32), nullable=False, default="pending", index=True)
    command_id = Column(String(36), nullable=True)
    target_session_id = Column(String(128), nullable=True)
    webui_url = Column(String(1024), nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<Feedback app={self.app_id!r} status={self.status!r}>"


class Bridge(Base):
    __tablename__ = "app_portal_bridges"

    device_id: Mapped[str] = Column(String(64), primary_key=True)
    hostname = Column(String(128), nullable=True)
    webui_base_url = Column(String(1024), nullable=True)
    server_key = Column(String(256), nullable=True)
    last_seen = Column(DateTime, nullable=True)
    registered_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Bridge device={self.device_id!r} webui={self.webui_base_url!r}>"

    __table_args__ = (
        UniqueConstraint("device_id", name="app_portal_bridge_unique"),
    )
