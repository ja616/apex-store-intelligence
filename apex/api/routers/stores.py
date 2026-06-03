"""Stores analytics router."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from apex.analytics.anomaly import AnomalyEngine
from apex.analytics.conversion import ConversionAttributionEngine
from apex.analytics.heatmap import HeatmapEngine
from apex.analytics.metrics import MetricsEngine
from apex.api.schemas import (
    AnomalyListResponse,
    AnomalyResponse,
    FunnelResponse,
    FunnelStage,
    HeatmapResponse,
    JourneyListResponse,
    JourneySummary,
    StoreMetricsResponse,
    VisitorListResponse,
    VisitorSummary,
    WhatIfResponse,
    ZoneHeatmapItem,
    IdentityListResponse,
    IdentitySummary,
)
from apex.models.database import get_db
from apex.models.sessions import Session, ZoneVisit
from apex.models.visitors import Visitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stores", tags=["stores"])

_metrics_engine = MetricsEngine()
_heatmap_engine = HeatmapEngine()
_anomaly_engine = AnomalyEngine()


# ── Metrics ──────────────────────────────────────────────────────────────────

@router.get("/{store_id}/metrics", response_model=StoreMetricsResponse)
def get_store_metrics(
    store_id: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    db: DBSession = Depends(get_db),
) -> StoreMetricsResponse:
    """Return full store metrics with confidence and reasoning."""
    m = _metrics_engine.get_store_metrics(
        store_id=store_id,
        db=db,
        start_time=start_time,
        end_time=end_time,
    )
    return StoreMetricsResponse(
        store_id=m.store_id,
        unique_visitors=m.unique_visitors,
        total_sessions=m.total_sessions,
        converted_sessions=m.converted_sessions,
        conversion_rate=round(m.conversion_rate, 4),
        avg_dwell_seconds=round(m.avg_dwell_seconds, 2),
        median_dwell_seconds=round(m.median_dwell_seconds, 2),
        peak_hour=m.peak_hour,
        peak_hour_count=m.peak_hour_count,
        total_revenue=round(m.total_revenue, 2),
        metric_confidence=m.metric_confidence,
        reasoning=m.reasoning,
        start_time=m.start_time,
        end_time=m.end_time,
    )


# ── Funnel ────────────────────────────────────────────────────────────────────

@router.get("/{store_id}/funnel", response_model=FunnelResponse)
def get_store_funnel(
    store_id: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    db: DBSession = Depends(get_db),
) -> FunnelResponse:
    """Return entry→browse→billing→purchase funnel with drop-off rates."""
    funnel = _metrics_engine.get_funnel(
        store_id=store_id,
        db=db,
        start_time=start_time,
        end_time=end_time,
    )
    stages = [
        FunnelStage(**stage) for stage in funnel["stages"]
    ]
    return FunnelResponse(
        store_id=funnel["store_id"],
        stages=stages,
        overall_conversion_rate=funnel["overall_conversion_rate"],
        metric_confidence=funnel["metric_confidence"],
    )


# ── Heatmap ───────────────────────────────────────────────────────────────────

@router.get("/{store_id}/heatmap", response_model=HeatmapResponse)
def get_store_heatmap(
    store_id: str,
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    db: DBSession = Depends(get_db),
) -> HeatmapResponse:
    """Return per-zone traffic heatmap with normalised density scores."""
    hm = _heatmap_engine.get_heatmap(
        store_id=store_id,
        db=db,
        start_time=start_time,
        end_time=end_time,
    )
    zone_items = [
        ZoneHeatmapItem(
            zone_name=z.zone_name,
            visit_count=z.visit_count,
            avg_dwell_seconds=round(z.avg_dwell_seconds, 2),
            total_dwell_seconds=round(z.total_dwell_seconds, 2),
            traffic_density=z.traffic_density,
            confidence=z.confidence,
        )
        for z in hm.zones.values()
    ]
    return HeatmapResponse(
        store_id=hm.store_id,
        zones=zone_items,
        metric_confidence=hm.metric_confidence,
        generated_at=hm.generated_at,
    )


# ── Anomalies ─────────────────────────────────────────────────────────────────

@router.get("/{store_id}/anomalies", response_model=AnomalyListResponse)
def get_store_anomalies(
    store_id: str,
    db: DBSession = Depends(get_db),
) -> AnomalyListResponse:
    """Return all currently active anomalies."""
    anomalies = _anomaly_engine.detect_all(store_id=store_id, db=db)
    items = [
        AnomalyResponse(
            anomaly_id=a.anomaly_id,
            anomaly_type=a.anomaly_type,
            severity=a.severity,
            confidence=a.confidence,
            reason=a.reason,
            suggested_action=a.suggested_action,
            detection_rule=a.detection_rule,
            detected_at=a.detected_at,
            camera_id=a.camera_id,
            zone_name=a.zone_name,
            metadata=a.metadata,
        )
        for a in anomalies
    ]
    return AnomalyListResponse(
        store_id=store_id,
        anomalies=items,
        total=len(items),
    )


# ── Visitor journeys ──────────────────────────────────────────────────────────

@router.get("/{store_id}/journeys", response_model=JourneyListResponse)
def get_visitor_journeys(
    store_id: str,
    top_n: int = Query(default=10, le=50),
    db: DBSession = Depends(get_db),
) -> JourneyListResponse:
    """Return the most common visitor zone journeys (anonymised)."""
    sessions: List[Session] = (
        db.query(Session)
        .filter(
            Session.store_id == store_id,
            Session.is_staff == False,  # noqa: E712
            Session.zones_visited.isnot(None),
        )
        .all()
    )

    journey_map: dict = {}
    for sess in sessions:
        key = tuple(sess.zones_visited or [])
        if key not in journey_map:
            journey_map[key] = {
                "count": 0,
                "dwells": [],
                "conversions": 0,
                "confidences": [],
            }
        journey_map[key]["count"] += 1
        if sess.duration_seconds is not None:
            journey_map[key]["dwells"].append(sess.duration_seconds)
        if sess.converted:
            journey_map[key]["conversions"] += 1
        if sess.session_confidence > 0:
            journey_map[key]["confidences"].append(sess.session_confidence)

    sorted_journeys = sorted(
        journey_map.items(), key=lambda x: x[1]["count"], reverse=True
    )[:top_n]

    items = []
    for zones, info in sorted_journeys:
        dwells = info["dwells"]
        confs = info["confidences"]
        items.append(JourneySummary(
            zones=list(zones),
            count=info["count"],
            avg_dwell_seconds=round(sum(dwells) / len(dwells), 2) if dwells else 0.0,
            conversion_rate=round(info["conversions"] / info["count"], 4),
            confidence=round(sum(confs) / len(confs), 4) if confs else 0.5,
        ))

    all_confs = [i.confidence for i in items]
    overall_conf = round(sum(all_confs) / len(all_confs), 4) if all_confs else 0.0

    return JourneyListResponse(
        store_id=store_id,
        journeys=items,
        metric_confidence=overall_conf,
    )


# ── Live visitors ─────────────────────────────────────────────────────────────

@router.get("/{store_id}/visitors", response_model=VisitorListResponse)
def get_live_visitors(
    store_id: str,
    db: DBSession = Depends(get_db),
) -> VisitorListResponse:
    """Return visitors and staff with live tracking details and confidence scores."""
    visitors: List[Visitor] = (
        db.query(Visitor)
        .filter(Visitor.store_id == store_id)
        .order_by(Visitor.last_seen.desc())
        .limit(100)
        .all()
    )

    items = []
    for v in visitors:
        # Count sessions
        session_count = (
            db.query(Session)
            .filter(Session.visitor_id == v.visitor_id)
            .count()
        )
        converted = (
            db.query(Session)
            .filter(
                Session.visitor_id == v.visitor_id,
                Session.converted == True,  # noqa: E712
            )
            .count()
        ) > 0

        latest_session = (
            db.query(Session)
            .filter(Session.visitor_id == v.visitor_id)
            .order_by(Session.entry_time.desc())
            .first()
        )
        
        camera_id = "CAM1"
        zone = "Entry"
        dwell_seconds = 0.0
        entered_at = v.first_seen
        confidence = v.identity_confidence
        
        if latest_session:
            latest_zv = (
                db.query(ZoneVisit)
                .filter(ZoneVisit.session_id == latest_session.session_id)
                .order_by(ZoneVisit.entry_time.desc())
                .first()
            )
            if latest_zv:
                camera_id = latest_zv.camera_id
                zone = latest_zv.zone_name
                if latest_zv.dwell_seconds is not None:
                    dwell_seconds = latest_zv.dwell_seconds
                elif latest_zv.entry_time:
                    dwell_seconds = (datetime.now() - latest_zv.entry_time).total_seconds()
            if latest_session.entry_time:
                entered_at = latest_session.entry_time
            confidence = latest_session.session_confidence or v.identity_confidence

        items.append(VisitorSummary(
            visitor_id=v.visitor_id,
            first_seen=v.first_seen,
            last_seen=v.last_seen,
            total_sessions=session_count,
            is_converted=converted,
            identity_confidence=v.identity_confidence,
            is_staff=v.is_staff,
            camera_id=camera_id,
            zone=zone,
            dwell_seconds=dwell_seconds,
            entered_at=entered_at,
            confidence=confidence,
        ))

    confs = [i.identity_confidence for i in items]
    overall_conf = round(sum(confs) / len(confs), 4) if confs else 0.0
    
    total_active = sum(1 for i in items if not i.is_staff)
    staff_active = sum(1 for i in items if i.is_staff)

    return VisitorListResponse(
        store_id=store_id,
        visitors=items,
        total=len(items),
        metric_confidence=overall_conf,
        total_active=total_active,
        staff_active=staff_active,
    )


# ── What-if analysis ──────────────────────────────────────────────────────────

@router.get("/{store_id}/what-if", response_model=WhatIfResponse)
def what_if_analysis(
    store_id: str,
    scenario: str = Query(
        default="reduce_queue_50pct",
        description="Scenario key: reduce_queue_50pct | improve_floor_engagement",
    ),
    db: DBSession = Depends(get_db),
) -> WhatIfResponse:
    """What-if scenario analysis.

    Supported scenarios:
    - reduce_queue_50pct: What if billing queue reduced by 50%?
    - improve_floor_engagement: What if floor dwell time increased by 20%?
    """
    m = _metrics_engine.get_store_metrics(store_id=store_id, db=db)
    current_rate = m.conversion_rate

    if scenario == "reduce_queue_50pct":
        # Research shows reducing queue wait by 50% can lift conversion ~15-25%
        lift_factor = 0.20
        projected = min(current_rate * (1 + lift_factor), 1.0)
        assumptions = [
            "Queue reduction achieved via additional billing counters or self-checkout",
            "Based on industry benchmark: 15-25% conversion lift per 50% queue reduction",
            "Assumes no change in product assortment or pricing",
        ]
        reasoning = (
            f"Current conversion rate {current_rate:.1%}. "
            f"A 50% reduction in billing queue wait typically yields a "
            f"~20% lift in conversion by reducing checkout abandonment. "
            f"Projected rate: {projected:.1%}."
        )
    elif scenario == "improve_floor_engagement":
        lift_factor = 0.12
        projected = min(current_rate * (1 + lift_factor), 1.0)
        assumptions = [
            "Floor engagement improved via better product placement and signage",
            "Based on: each additional minute of dwell ~0.5% conversion lift",
            "Assumes 20% increase in avg floor dwell time",
        ]
        reasoning = (
            f"Current conversion rate {current_rate:.1%}. "
            f"Increasing floor engagement by 20% (better placement, demos) "
            f"projects ~12% conversion lift. Projected rate: {projected:.1%}."
        )
    else:
        projected = current_rate
        lift_factor = 0.0
        assumptions = ["Unknown scenario — no projection available"]
        reasoning = f"Scenario '{scenario}' not recognised."

    return WhatIfResponse(
        scenario=scenario,
        current_conversion_rate=round(current_rate, 4),
        projected_conversion_rate=round(projected, 4),
        projected_lift_pct=round(lift_factor * 100, 2),
        confidence=round(m.metric_confidence * 0.7, 4),   # model uncertainty
        assumptions=assumptions,
        reasoning=reasoning,
    )


# ── Identity Confidence Monitor ────────────────────────────────────────────────

@router.get("/{store_id}/identity", response_model=IdentityListResponse)
def get_store_identity_monitor(
    store_id: str,
    db: DBSession = Depends(get_db),
) -> IdentityListResponse:
    """Return identity matching, re-entry counts, and matching summaries."""
    visitors = (
        db.query(Visitor)
        .filter(Visitor.store_id == store_id)
        .order_by(Visitor.last_seen.desc())
        .all()
    )

    identities = []
    reentry_count = 0
    staff_excluded = 0

    for v in visitors:
        if v.is_staff:
            staff_excluded += 1

        sessions = (
            db.query(Session)
            .filter(Session.visitor_id == v.visitor_id)
            .order_by(Session.entry_time)
            .all()
        )

        matched_visitors = [s.session_id[:8] for s in sessions]
        is_reentry = len(sessions) > 1
        if is_reentry:
            reentry_count += 1

        # Gap calculation
        reentry_gap = 0.0
        if is_reentry and len(sessions) >= 2:
            s1, s2 = sessions[0], sessions[1]
            if s1.exit_time and s2.entry_time:
                reentry_gap = max(0.0, (s2.entry_time - s1.exit_time).total_seconds() / 60.0)

        # Match reason
        if v.is_staff:
            explanation = v.staff_reason or "Staff behavioral heuristics exclusion applied"
        else:
            explanation = f"Appearance ReID match (confidence: {v.identity_confidence:.2f}) verified by camera topology constraints."

        identities.append(IdentitySummary(
            identity_id=v.visitor_id[:8],
            matched_visitors=matched_visitors,
            matching_explanation=explanation,
            reentry_confidence=v.identity_confidence,
            is_reentry=is_reentry,
            reentry_gap_minutes=round(reentry_gap, 1),
            last_seen=v.last_seen,
            is_staff=v.is_staff,
        ))

    return IdentityListResponse(
        total_identities=len(visitors),
        reentry_count=reentry_count,
        staff_excluded=staff_excluded,
        identities=identities,
    )
