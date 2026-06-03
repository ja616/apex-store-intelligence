"""POS Transaction model and helpers."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from apex.models.database import Base


class Transaction(Base):
    """A single POS transaction row, optionally attributed to a visitor session."""

    __tablename__ = "transactions"

    # ── Primary key ──────────────────────────────────────────────────────────
    # We use the original invoice_number from the POS CSV as a natural key when
    # available; fall back to a generated UUID.
    transaction_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )

    # ── Store ────────────────────────────────────────────────────────────────
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # ── Timing ───────────────────────────────────────────────────────────────
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )

    # ── Financial ────────────────────────────────────────────────────────────
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # NMV (Net Merchandise Value) = amount after discounts
    nmv: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # ── Product / customer ───────────────────────────────────────────────────
    customer_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    customer_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    brand_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sub_category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    salesperson_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # ── Attribution ──────────────────────────────────────────────────────────
    attributed_visitor_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    attributed_session_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    attribution_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    attribution_reason: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    is_attributed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # ── Raw CSV payload ───────────────────────────────────────────────────────
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # ── Audit ────────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_transactions_store_ts", "store_id", "timestamp"),
        Index("ix_transactions_attributed", "is_attributed", "store_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Transaction {self.transaction_id} "
            f"amount={self.amount:.2f} "
            f"attributed={self.is_attributed} "
            f"conf={self.attribution_confidence:.2f}>"
        )
