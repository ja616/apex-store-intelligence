"""Health check router."""
from __future__ import annotations

import time
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from apex.api.schemas import HealthResponse
from apex.models.database import get_db
from apex.models.events import Event

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health_check(db: DBSession = Depends(get_db)) -> HealthResponse:
    """Liveness + readiness probe.

    Returns:
      - DB connectivity status
      - Event freshness (seconds since last event)
      - Model availability
      - Response latency
      - Overall confidence (1.0 = fully healthy)
    """
    t0 = time.perf_counter()
    db_status = "ok"
    event_freshness: float | None = None
    model_status = "available"
    confidence = 1.0

    # ── DB check ──────────────────────────────────────────────────────────────
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"
        confidence -= 0.5

    # ── Event freshness ───────────────────────────────────────────────────────
    try:
        latest: Event | None = (
            db.query(Event)
            .order_by(Event.timestamp.desc())
            .first()
        )
        if latest:
            event_freshness = (
                datetime.utcnow() - latest.timestamp
            ).total_seconds()
            if event_freshness > 600:   # > 10 min
                confidence -= 0.2
        else:
            event_freshness = None
            confidence -= 0.1   # no events yet
    except Exception:
        pass

    # ── Model check ───────────────────────────────────────────────────────────
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        model_status = "ultralytics_unavailable"
        confidence -= 0.1

    latency_ms = (time.perf_counter() - t0) * 1000

    overall = "healthy" if confidence >= 0.7 else "degraded"
    if db_status != "ok":
        overall = "unhealthy"

    return HealthResponse(
        status=overall,
        db_status=db_status,
        event_freshness_seconds=round(event_freshness, 1) if event_freshness is not None else None,
        model_status=model_status,
        latency_ms=round(latency_ms, 2),
        confidence=round(max(confidence, 0.0), 3),
        timestamp=datetime.utcnow(),
    )
