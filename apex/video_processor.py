"""End-to-end video processor orchestrator.

Pipeline: Detect → Track → Embed → Identify → Emit Events → Write to DB
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

from apex.config import settings
from apex.models.database import SessionLocal
from apex.models.events import Event, EventType
from apex.models.visitors import Visitor

logger = logging.getLogger(__name__)

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logger.warning("cv2 not available — VideoProcessor will not process real videos")

try:
    import numpy as np
    _NP_AVAILABLE = True
except ImportError:
    _NP_AVAILABLE = False


_BATCH_SIZE = 50   # write events to DB in batches of this size


@dataclass
class ProcessingResult:
    """Summary of a completed video processing run."""
    events_generated: int = 0
    visitors_detected: int = 0
    processing_time_seconds: float = 0.0
    fps: float = 0.0
    model_used: str = ""
    camera_id: str = ""
    video_path: str = ""
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class VideoProcessor:
    """Orchestrates the full detection → identity → event pipeline for one video.

    Designed to be called from the API or CLI.  Writes events to the DB in
    batches of _BATCH_SIZE and supports a progress callback for SSE streaming.
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.model_name = model_name or settings.detector_model
        self.device = device or settings.detector_device
        self.progress_cb = progress_cb

        # Lazy-load heavy components (so imports don't fail in test env)
        self._detector = None
        self._tracker = None
        self._embedder = None
        self._identity_engine = None
        self._topology = None

    def _ensure_pipeline(self) -> bool:
        """Initialise pipeline components on first call. Returns True if OK."""
        if self._detector is not None:
            return True
        try:
            from apex.pipeline.detector import PersonDetector
            from apex.pipeline.tracker import ByteTracker
            from apex.pipeline.embeddings import AppearanceEmbedder
            from apex.pipeline.identity_engine import IdentityEngine
            from apex.pipeline.topology import CameraTopologyService

            self._topology = CameraTopologyService(settings.topology_config)
            self._detector = PersonDetector(
                model_name=self.model_name,
                confidence=settings.detector_confidence,
                device=self.device,
            )
            self._tracker = ByteTracker(
                model_name=self.model_name,
                confidence=settings.detector_confidence,
                device=self.device,
            )
            self._embedder = AppearanceEmbedder(device=self.device)
            self._identity_engine = IdentityEngine(
                embedder=self._embedder,
                topology=self._topology,
                similarity_threshold=settings.reid_similarity_threshold,
                temporal_window_seconds=settings.reid_temporal_window_seconds,
            )
            return True
        except Exception as exc:
            logger.error("Pipeline init failed: %s", exc)
            return False

    def process_video(
        self,
        video_path: str,
        camera_id: str,
        store_id: str,
        start_timestamp: Optional[datetime] = None,
        max_frames: Optional[int] = None,
    ) -> ProcessingResult:
        """Process a single video file.

        Args:
            video_path:       Absolute path to the .mp4 file.
            camera_id:        Camera identifier (e.g. "CAM1").
            store_id:         Store identifier.
            start_timestamp:  Real-world time of the first frame.
            max_frames:       Limit frames processed (for testing).

        Returns:
            ProcessingResult with stats and error info.
        """
        t0 = time.perf_counter()
        result = ProcessingResult(
            camera_id=camera_id,
            video_path=video_path,
            model_used=self.model_name,
        )

        if not _CV2_AVAILABLE:
            result.error = "cv2 not available — install opencv-python-headless"
            return result

        if not self._ensure_pipeline():
            result.error = "Pipeline initialisation failed"
            return result

        try:
            import cv2  # noqa: PLC0415
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                result.error = f"Cannot open video: {video_path}"
                return result

            fps_src = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            start_ts = start_timestamp or datetime.now(timezone.utc)

            events_buffer: List[Event] = []
            known_visitors: set = set()
            frame_idx = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if max_frames and frame_idx >= max_frames:
                    break

                ts_secs = frame_idx / fps_src
                frame_ts = datetime.fromtimestamp(
                    start_ts.timestamp() + ts_secs, tz=timezone.utc
                ).replace(tzinfo=None)

                # ── Detect + track ────────────────────────────────────────────
                tracked_objs = self._tracker.update(frame, frame_idx)

                for tracked in tracked_objs:
                    if tracked.is_lost:
                        continue   # skip lost tracks for event generation

                    # ── Extract embedding ─────────────────────────────────────
                    embedding = self._embedder.extract(frame, tracked.bbox)

                    # ── Identify ───────────────────────────────────────────────
                    match = self._identity_engine.match(
                        embedding=embedding,
                        camera_id=camera_id,
                        timestamp=frame_ts,
                    )

                    visitor_id = match.visitor_id
                    known_visitors.add(visitor_id)

                    # ── Determine event type ──────────────────────────────────
                    if match.reentry_confidence > 0.5:
                        ev_type = EventType.REENTRY_DETECTED
                    elif camera_id in settings.billing_zone_cameras:
                        ev_type = EventType.BILLING_ZONE_ENTERED
                    elif camera_id in settings.entry_cameras and match.is_new_identity:
                        ev_type = EventType.PERSON_ENTERED
                    else:
                        ev_type = EventType.PERSON_DETECTED

                    x1, y1, x2, y2 = tracked.bbox
                    event = Event(
                        event_id=str(uuid.uuid4()),
                        store_id=store_id,
                        camera_id=camera_id,
                        visitor_id=visitor_id,
                        event_type=ev_type.value,
                        timestamp=frame_ts,
                        confidence=tracked.confidence,
                        identity_confidence=match.identity_confidence,
                        is_staff=False,
                        bbox_x=x1,
                        bbox_y=y1,
                        bbox_w=x2 - x1,
                        bbox_h=y2 - y1,
                        metadata_json={
                            "track_id": tracked.track_id,
                            "frame_idx": frame_idx,
                            "match_explanation": match.matching_explanation,
                            "reentry_confidence": match.reentry_confidence,
                        },
                        schema_version=1,
                    )
                    events_buffer.append(event)

                # ── Batch write ───────────────────────────────────────────────
                if len(events_buffer) >= _BATCH_SIZE:
                    self._flush_events(events_buffer)
                    result.events_generated += len(events_buffer)
                    events_buffer.clear()

                # ── Progress callback ─────────────────────────────────────────
                if self.progress_cb and frame_idx % 50 == 0 and total_frames > 0:
                    pct = round(frame_idx / total_frames * 100, 1)
                    self.progress_cb({
                        "frame": frame_idx,
                        "total": total_frames,
                        "percent": pct,
                        "events": result.events_generated + len(events_buffer),
                    })

                frame_idx += 1

            cap.release()

            # Flush remaining
            if events_buffer:
                self._flush_events(events_buffer)
                result.events_generated += len(events_buffer)

            # Reset tracker between videos
            if self._tracker:
                self._tracker.reset()

            elapsed = time.perf_counter() - t0
            result.processing_time_seconds = round(elapsed, 2)
            result.fps = round(frame_idx / elapsed, 2) if elapsed > 0 else 0.0
            result.visitors_detected = len(known_visitors)

        except Exception as exc:
            logger.exception("VideoProcessor error: %s", exc)
            result.error = str(exc)

        return result

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _flush_events(self, events: List[Event]) -> None:
        """Write a batch of events to the DB with idempotency."""
        if not events:
            return
        db = SessionLocal()
        try:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            from sqlalchemy import text

            for ev in events:
                # Idempotency: skip duplicate event_ids
                existing = db.get(Event, ev.event_id)
                if existing is None:
                    db.add(ev)
            db.commit()
        except Exception as exc:
            logger.error("Event flush error: %s", exc)
            db.rollback()
        finally:
            db.close()
