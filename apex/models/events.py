"""Immutable event ledger — every detection/transition/anomaly becomes an Event row."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from apex.models.database import Base


class EventType(str, Enum):
    PERSON_DETECTED = "PERSON_DETECTED"
    PERSON_ENTERED = "PERSON_ENTERED"
    PERSON_EXITED = "PERSON_EXITED"
    ZONE_TRANSITION = "ZONE_TRANSITION"
    BILLING_ZONE_ENTERED = "BILLING_ZONE_ENTERED"
    BILLING_ZONE_EXITED = "BILLING_ZONE_EXITED"
    STAFF_DETECTED = "STAFF_DETECTED"
    REENTRY_DETECTED = "REENTRY_DETECTED"


class Event(Base):
    """Append-only event ledger.

    All downstream metrics are computed from this table; raw frames are never
    re-scanned after initial ingestion.
    """

    __tablename__ = "events"

    # ── Primary key ──────────────────────────────────────────────────────────
    event_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # ── Context ──────────────────────────────────────────────────────────────
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    visitor_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )

    # ── Classification ───────────────────────────────────────────────────────
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True,
        server_default=func.now(),
    )

    # ── Confidence chain ─────────────────────────────────────────────────────
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    identity_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # ── Staff flag ───────────────────────────────────────────────────────────
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Bounding box (pixel coords, relative to frame) ───────────────────────
    bbox_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Arbitrary payload ────────────────────────────────────────────────────
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True
    )

    # ── Schema versioning ────────────────────────────────────────────────────
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # ── Audit ────────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    # ── Indexes ──────────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_events_store_ts", "store_id", "timestamp"),
        Index("ix_events_visitor_ts", "visitor_id", "timestamp"),
        Index("ix_events_camera_ts", "camera_id", "timestamp"),
        Index("ix_events_type_store", "event_type", "store_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Event {self.event_id[:8]} "
            f"type={self.event_type} "
            f"cam={self.camera_id} "
            f"conf={self.confidence:.2f}>"
        )
