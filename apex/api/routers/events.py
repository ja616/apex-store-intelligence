"""Events router — ingest and replay events."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from apex.api.schemas import EventIngestionRequest, EventIngestionResponse
from apex.models.database import get_db
from apex.models.events import Event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("/ingest", response_model=EventIngestionResponse)
def ingest_events(
    request: EventIngestionRequest,
    db: DBSession = Depends(get_db),
) -> EventIngestionResponse:
    """Bulk-ingest events.  Duplicate event_ids are silently skipped."""
    accepted = 0
    skipped = 0
    total_confidence = 0.0

    for item in request.events:
        existing = db.get(Event, item.event_id)
        if existing is not None:
            skipped += 1
            continue

        bbox = item.bbox
        event = Event(
            event_id=item.event_id,
            store_id=item.store_id,
            camera_id=item.camera_id,
            visitor_id=item.visitor_id,
            session_id=item.session_id,
            event_type=item.event_type,
            timestamp=item.timestamp,
            confidence=item.confidence,
            identity_confidence=item.identity_confidence,
            is_staff=item.is_staff,
            bbox_x=bbox.x if bbox else None,
            bbox_y=bbox.y if bbox else None,
            bbox_w=bbox.w if bbox else None,
            bbox_h=bbox.h if bbox else None,
            metadata_json=item.metadata,
            schema_version=item.schema_version,
        )
        db.add(event)
        accepted += 1
        total_confidence += item.confidence

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB commit failed: {exc}") from exc

    avg_conf = round(total_confidence / accepted, 4) if accepted > 0 else 0.0

    return EventIngestionResponse(
        accepted=accepted,
        skipped_duplicates=skipped,
        confidence_avg=avg_conf,
        message=f"Accepted {accepted} events, skipped {skipped} duplicates.",
    )


@router.get("/replay/{store_id}")
async def replay_events(
    store_id: str,
    limit: int = Query(default=500, le=5000),
    db: DBSession = Depends(get_db),
) -> StreamingResponse:
    """SSE stream of events for dashboard simulation.

    Streams events in chronological order with Server-Sent Events format.
    """
    events: List[Event] = (
        db.query(Event)
        .filter(Event.store_id == store_id)
        .order_by(Event.timestamp)
        .limit(limit)
        .all()
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        for ev in events:
            data = {
                "event_id": ev.event_id,
                "camera_id": ev.camera_id,
                "visitor_id": ev.visitor_id,
                "event_type": ev.event_type,
                "timestamp": ev.timestamp.isoformat(),
                "confidence": ev.confidence,
                "identity_confidence": ev.identity_confidence,
                "is_staff": ev.is_staff,
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.01)   # slight delay for realistic streaming
        yield "data: {\"type\": \"stream_end\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Recent Events Ticker ──────────────────────────────────────────────────────

@router.get("/recent", response_model=List[dict])
def get_recent_events(
    store_id: str = "brigade-road-bangalore",
    limit: int = 15,
    db: DBSession = Depends(get_db),
) -> List[dict]:
    """Return the most recent events in the database for the live ticker."""
    events = (
        db.query(Event)
        .filter(Event.store_id == store_id)
        .order_by(Event.timestamp.desc())
        .limit(limit)
        .all()
    )

    items = []
    # Map event types to simplified UI representations
    type_map = {
        "PERSON_ENTERED": "ENTRY",
        "PERSON_EXITED": "EXIT",
        "ZONE_TRANSITION": "ZONE_CHANGE",
        "BILLING_ZONE_ENTERED": "ZONE_CHANGE",
        "BILLING_ZONE_EXITED": "ZONE_CHANGE",
        "REENTRY_DETECTED": "ENTRY",
        "STAFF_DETECTED": "ZONE_CHANGE",
    }

    for idx, ev in enumerate(events):
        ui_type = type_map.get(ev.event_type, "ZONE_CHANGE")
        # Generate friendly label for zone
        zone_label = ev.camera_id
        if ev.camera_id == "CAM1":
            zone_label = "Entry Gate"
        elif ev.camera_id == "CAM2":
            zone_label = "Floor Zone A"
        elif ev.camera_id == "CAM3":
            zone_label = "Floor Zone B"
        elif ev.camera_id == "CAM4":
            zone_label = "Billing Counter A"
        elif ev.camera_id == "CAM5":
            zone_label = "Billing Counter B"

        items.append({
            "id": idx + 1,
            "type": ui_type,
            "visitor_id": f"VIS-{ev.visitor_id[:4]}" if ev.visitor_id else "VIS-UNKNOWN",
            "zone": zone_label,
            "time": "Recent",
            "confidence": ev.confidence,
        })

    # If database is empty, return a friendly placeholder warning
    if not items:
        items = [{
            "id": 1,
            "type": "ANOMALY",
            "visitor_id": "SYS-ALERT",
            "zone": "No events found in ledger",
            "time": "Now",
            "confidence": 1.0,
        }]

    return items
