"""Pydantic schemas for all API request/response types.

Every schema that represents a metric or detection must have:
  - confidence: float  (0-1)
  - reasoning / reason: str or dict
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ── Shared building blocks ────────────────────────────────────────────────────

class ConfidenceBreakdown(BaseModel):
    """Detailed confidence signal breakdown."""
    appearance_similarity: float = 0.0
    topology_score: float = 0.0
    temporal_score: float = 0.0
    overall: float = 0.0
    reasoning: str = ""


class BBoxSchema(BaseModel):
    x: float
    y: float
    w: float
    h: float


# ── Event schemas ─────────────────────────────────────────────────────────────

class EventIngestionItem(BaseModel):
    """Single event for bulk ingestion."""
    event_id: str
    store_id: str
    camera_id: str
    visitor_id: Optional[str] = None
    session_id: Optional[str] = None
    event_type: str
    timestamp: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    identity_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_staff: bool = False
    bbox: Optional[BBoxSchema] = None
    metadata: Optional[Dict[str, Any]] = None
    schema_version: int = 1


class EventIngestionRequest(BaseModel):
    events: List[EventIngestionItem]


class EventIngestionResponse(BaseModel):
    accepted: int
    skipped_duplicates: int
    confidence_avg: float
    message: str


# ── Store metrics schemas ──────────────────────────────────────────────────────

class StoreMetricsResponse(BaseModel):
    store_id: str
    unique_visitors: int
    total_sessions: int
    converted_sessions: int
    conversion_rate: float
    avg_dwell_seconds: float
    median_dwell_seconds: float
    peak_hour: Optional[int]
    peak_hour_count: int
    total_revenue: float
    metric_confidence: float
    reasoning: Dict[str, Any]
    start_time: Optional[datetime]
    end_time: Optional[datetime]


# ── Funnel schemas ─────────────────────────────────────────────────────────────

class FunnelStage(BaseModel):
    stage: str
    count: int
    confidence: float
    drop_off_pct: float


class FunnelResponse(BaseModel):
    store_id: str
    stages: List[FunnelStage]
    overall_conversion_rate: float
    metric_confidence: float


# ── Heatmap schemas ────────────────────────────────────────────────────────────

class ZoneHeatmapItem(BaseModel):
    zone_name: str
    visit_count: int
    avg_dwell_seconds: float
    total_dwell_seconds: float
    traffic_density: float   # 0–100
    confidence: float


class HeatmapResponse(BaseModel):
    store_id: str
    zones: List[ZoneHeatmapItem]
    metric_confidence: float
    generated_at: Optional[datetime]


# ── Anomaly schemas ────────────────────────────────────────────────────────────

class AnomalyResponse(BaseModel):
    anomaly_id: str
    anomaly_type: str
    severity: str
    confidence: float
    reason: str
    suggested_action: str
    detection_rule: str
    detected_at: datetime
    camera_id: Optional[str]
    zone_name: Optional[str]
    metadata: Dict[str, Any] = {}


class AnomalyListResponse(BaseModel):
    store_id: str
    anomalies: List[AnomalyResponse]
    total: int


# ── Health schemas ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    db_status: str
    event_freshness_seconds: Optional[float]
    model_status: str
    latency_ms: float
    confidence: float
    timestamp: datetime


# ── Video processing schemas ───────────────────────────────────────────────────

class VideoProcessingRequest(BaseModel):
    camera_id: str
    store_id: str
    start_timestamp: Optional[datetime] = None
    model_name: Optional[str] = None
    max_frames: Optional[int] = None


class VideoProcessingResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str              # pending | running | done | failed
    progress_pct: float
    events_generated: int
    visitors_detected: int
    processing_time_seconds: float
    fps: float
    model_used: str
    error: Optional[str]
    result: Optional[Dict[str, Any]] = None


# ── Visitor / journey schemas ──────────────────────────────────────────────────

class VisitorSummary(BaseModel):
    visitor_id: str
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    total_sessions: int
    is_converted: bool
    identity_confidence: float
    is_staff: bool = False
    camera_id: Optional[str] = None
    zone: Optional[str] = None
    dwell_seconds: Optional[float] = None
    entered_at: Optional[datetime] = None
    confidence: float = 1.0


class VisitorListResponse(BaseModel):
    store_id: str
    visitors: List[VisitorSummary]
    total: int
    metric_confidence: float
    total_active: int = 0
    staff_active: int = 0


class JourneySummary(BaseModel):
    zones: List[str]
    count: int          # how many visitors followed this journey
    avg_dwell_seconds: float
    conversion_rate: float
    confidence: float


class JourneyListResponse(BaseModel):
    store_id: str
    journeys: List[JourneySummary]
    metric_confidence: float


# ── What-if schema ─────────────────────────────────────────────────────────────

class WhatIfResponse(BaseModel):
    scenario: str
    current_conversion_rate: float
    projected_conversion_rate: float
    projected_lift_pct: float
    confidence: float
    assumptions: List[str]
    reasoning: str


# ── Identity schemas ───────────────────────────────────────────────────────────

class IdentitySummary(BaseModel):
    identity_id: str
    matched_visitors: List[str]
    matching_explanation: str
    reentry_confidence: float
    is_reentry: bool
    reentry_gap_minutes: float
    last_seen: datetime
    is_staff: bool = False


class IdentityListResponse(BaseModel):
    total_identities: int
    reentry_count: int
    staff_excluded: int
    identities: List[IdentitySummary]
