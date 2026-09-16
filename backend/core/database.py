import logging
import sys
from collections.abc import Iterator
from typing import Any, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from backend.core import config

logger = logging.getLogger(__name__)

Base = declarative_base()

# Session management placeholders
_engine: Optional[Engine] = None
_Session: Optional[sessionmaker[Session]] = None

def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine
        
    if not config.DATABASE_URL:
        logger.error("Database connection URL is not set.")
        logger.error("Please start the application with a valid configuration file (--config).")
        sys.exit(1)
        
    # Pick JSON/JSONB type implementation depending on dialect
    # SQLAlchemy maps sqlalchemy.types.JSON automatically, but for PostgreSQL, we can use JSONB for performance.
    # Note: SQLAlchemy's create_engine is lazy, so we initialize it here.
    
    _engine = create_engine(config.DATABASE_URL)
    
    # Configure SQLite-specific settings (like WAL mode)
    if _engine.name == 'sqlite':
        @event.listens_for(_engine, 'connect')
        def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA busy_timeout = 5000;")
            if config.SQLITE_WAL:
                cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.close()
                
    return _engine

def get_session() -> Session:
    global _Session
    if _Session is None:
        engine = get_engine()
        init_db()
        _Session = sessionmaker(bind=engine)
    return _Session()

def init_db() -> None:
    """Initializes tables in the target database if they do not exist."""
    engine = get_engine()
    Base.metadata.create_all(engine)

from contextlib import contextmanager

def get_db() -> Iterator[Session]:
    """FastAPI dependency for database session lifecycle management."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations (for CLI/scripts)."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
