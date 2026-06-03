"""Visitor model — persistent identity across sessions."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from apex.models.database import Base


class Visitor(Base):
    """One row per unique person identity observed in the store.

    The identity_confidence reflects how certain the system is that all
    appearances mapped to this row truly belong to the same physical person.
    """

    __tablename__ = "visitors"

    # ── Identity ─────────────────────────────────────────────────────────────
    visitor_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # ── Time window ──────────────────────────────────────────────────────────
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )

    # ── Staff classification ──────────────────────────────────────────────────
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    staff_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    staff_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # ── Appearance embedding (rolling gallery of last N embeddings) ───────────
    embedding_vector: Mapped[Optional[List[Any]]] = mapped_column(
        JSON, nullable=True
    )   # stored as list-of-lists (one 128-dim vector per appearance)

    # ── Visit stats ───────────────────────────────────────────────────────────
    total_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    identity_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )

    # ── Audit ────────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        tag = "STAFF" if self.is_staff else "VISITOR"
        return (
            f"<Visitor {self.visitor_id[:8]} "
            f"[{tag}] conf={self.identity_confidence:.2f} "
            f"visits={self.total_visits}>"
        )
