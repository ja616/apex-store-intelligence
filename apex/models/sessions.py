"""Session and ZoneVisit models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from apex.models.database import Base


class Session(Base):
    """One row per contiguous visit of a visitor to the store.

    A re-entry creates a new Session for the same visitor_id.
    """

    __tablename__ = "sessions"

    # ── Primary key ──────────────────────────────────────────────────────────
    session_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Context ──────────────────────────────────────────────────────────────
    visitor_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # ── Timing ───────────────────────────────────────────────────────────────
    entry_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    exit_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Conversion ───────────────────────────────────────────────────────────
    converted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attribution_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    attribution_reason: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )

    # ── Journey ──────────────────────────────────────────────────────────────
    zones_visited: Mapped[Optional[List[Any]]] = mapped_column(
        JSON, nullable=True
    )   # list of zone names in order

    # ── Session confidence ────────────────────────────────────────────────────
    session_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # ── Re-entry tracking ────────────────────────────────────────────────────
    reentry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Staff ────────────────────────────────────────────────────────────────
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Audit ────────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    zone_visits: Mapped[List["ZoneVisit"]] = relationship(
        "ZoneVisit", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sessions_store_entry", "store_id", "entry_time"),
        Index("ix_sessions_visitor_entry", "visitor_id", "entry_time"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Session {self.session_id[:8]} "
            f"visitor={self.visitor_id[:8]} "
            f"converted={self.converted} "
            f"conf={self.session_confidence:.2f}>"
        )


class ZoneVisit(Base):
    """One row per zone dwell segment within a session."""

    __tablename__ = "zone_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    camera_id: Mapped[str] = mapped_column(String(16), nullable=False)
    zone_name: Mapped[str] = mapped_column(String(64), nullable=False)

    entry_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    exit_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Confidence ────────────────────────────────────────────────────────────
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── Relationship ──────────────────────────────────────────────────────────
    session: Mapped["Session"] = relationship("Session", back_populates="zone_visits")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ZoneVisit session={self.session_id[:8]} "
            f"zone={self.zone_name} "
            f"dwell={self.dwell_seconds}s>"
        )
