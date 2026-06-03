"""ByteTrack wrapper using ultralytics built-in tracking.

Gracefully stubs when ultralytics is unavailable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
    _ULTRALYTICS_AVAILABLE = True
except ImportError:
    _ULTRALYTICS_AVAILABLE = False

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


@dataclass
class TrackedObject:
    """A tracked person bounding box with a persistent track_id."""
    track_id: int
    bbox: List[float]          # [x1, y1, x2, y2]
    confidence: float
    age: int                   # frames since first seen
    hits: int                  # total confirmed detections
    class_id: int = 0
    is_lost: bool = False      # True = track was lost (no detection this frame)


class ByteTracker:
    """Wraps Ultralytics ByteTrack tracking.

    Each call to ``update()`` returns the current list of tracked objects.
    Lost tracks are kept in memory for ``max_lost`` frames to allow
    within-camera re-ID before being discarded.
    """

    def __init__(
        self,
        model_name: str = "yolo11n.pt",
        confidence: float = 0.4,
        device: str = "cpu",
        max_lost: int = 30,
        tracker_config: str = "bytetrack.yaml",
    ) -> None:
        self.model_name = model_name
        self.confidence = confidence
        self.device = device
        self.max_lost = max_lost
        self.tracker_config = tracker_config
        self._model = None
        self._stub = False

        # Internal bookkeeping for lost tracks
        self._last_tracks: dict[int, TrackedObject] = {}
        self._lost_age: dict[int, int] = {}   # track_id -> frames lost

        self._init_model()

    def _init_model(self) -> None:
        if not _ULTRALYTICS_AVAILABLE:
            logger.warning("ByteTracker running in stub mode.")
            self._stub = True
            return
        try:
            import numpy as np
            self._model = YOLO(self.model_name)
            self._model.to(self.device)
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._model(dummy, verbose=False)
            logger.info("ByteTracker loaded: model=%s", self.model_name)
        except Exception as exc:
            logger.error("ByteTracker init failed: %s — stub mode", exc)
            self._stub = True
            self._model = None

    def update(
        self,
        frame: np.ndarray,
        frame_idx: int = 0,
    ) -> List[TrackedObject]:
        """Run detection + tracking on a single frame.

        Returns all currently active tracked objects (including briefly-lost
        ones within max_lost window).
        """
        if self._stub or self._model is None:
            return []

        try:
            results = self._model.track(
                frame,
                persist=True,
                conf=self.confidence,
                classes=[0],   # person only
                tracker=self.tracker_config,
                verbose=False,
            )
        except Exception as exc:
            logger.error("Tracking error frame=%d: %s", frame_idx, exc)
            return []

        active_ids: set[int] = set()
        tracked: List[TrackedObject] = []

        for result in results:
            if result.boxes is None or result.boxes.id is None:
                continue
            for box, track_id_tensor, conf_tensor in zip(
                result.boxes.xyxy,
                result.boxes.id,
                result.boxes.conf,
            ):
                track_id = int(track_id_tensor.item())
                conf = float(conf_tensor.item())
                bbox = box.tolist()
                active_ids.add(track_id)

                # Update bookkeeping
                prev = self._last_tracks.get(track_id)
                age = (prev.age + 1) if prev else 1
                hits = (prev.hits + 1) if prev else 1
                obj = TrackedObject(
                    track_id=track_id,
                    bbox=bbox,
                    confidence=conf,
                    age=age,
                    hits=hits,
                    is_lost=False,
                )
                self._last_tracks[track_id] = obj
                self._lost_age.pop(track_id, None)
                tracked.append(obj)

        # Handle lost tracks (keep briefly for re-ID)
        for tid, obj in list(self._last_tracks.items()):
            if tid not in active_ids:
                lost_frames = self._lost_age.get(tid, 0) + 1
                if lost_frames <= self.max_lost:
                    self._lost_age[tid] = lost_frames
                    lost_obj = TrackedObject(
                        track_id=tid,
                        bbox=obj.bbox,
                        confidence=obj.confidence * 0.7,
                        age=obj.age + 1,
                        hits=obj.hits,
                        is_lost=True,
                    )
                    tracked.append(lost_obj)
                else:
                    del self._last_tracks[tid]
                    self._lost_age.pop(tid, None)

        return tracked

    def reset(self) -> None:
        """Reset tracker state between videos."""
        self._last_tracks.clear()
        self._lost_age.clear()
        if self._model is not None:
            try:
                # Reset ultralytics internal tracker state
                self._model.predictor = None
            except Exception:
                pass
