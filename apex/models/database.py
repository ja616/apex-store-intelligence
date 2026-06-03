"""SQLAlchemy 2.0 database setup — SQLite default, PostgreSQL via DATABASE_URL env var."""
from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from apex.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=False,
    future=True,
)

# Enable WAL mode + foreign keys for SQLite
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# Dependency / helper
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and closes it after."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call multiple times (idempotent)."""
    # Import all models so that Base.metadata is populated before create_all
    import apex.models.events  # noqa: F401
    import apex.models.visitors  # noqa: F401
    import apex.models.sessions  # noqa: F401
    import apex.models.transactions  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialised — url=%s", settings.database_url)
