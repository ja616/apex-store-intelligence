"""Person detector wrapping YOLOv11n / RT-DETR via Ultralytics.

Falls back gracefully when ultralytics / torch is absent (e.g. test-only env).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, ClassVar, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Optional heavy imports ────────────────────────────────────────────────────
try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    logger.warning("torch not available — detector will run in stub mode")

try:
    from ultralytics import YOLO
    _ULTRALYTICS_AVAILABLE = True
except ImportError:
    _ULTRALYTICS_AVAILABLE = False
    logger.warning("ultralytics not available — detector will run in stub mode")

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Detection:
    """Single person detection result from one frame."""
    bbox: List[float]          # [x1, y1, x2, y2] in pixels
    confidence: float          # detection confidence 0-1
    class_id: int              # always 0 (person)
    frame_idx: int             # 0-based frame index within the video
    timestamp: float           # seconds from video start


# ── Detector ─────────────────────────────────────────────────────────────────

class PersonDetector:
    """YOLOv11n (or RT-DETR-L) person detector.

    Usage::

        detector = PersonDetector("yolo11n.pt", confidence=0.4, device="cpu")
        detections = detector.detect(frame_bgr)
    """

    PERSON_CLASS_ID: ClassVar[int] = 0   # COCO class 0 = person

    def __init__(
        self,
        model_name: str = "yolo11n.pt",
        confidence: float = 0.4,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.confidence_threshold = confidence
        self.device = device
        self._model = None
        self._stub_mode = False
        self._load_model()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        if not (_ULTRALYTICS_AVAILABLE and _TORCH_AVAILABLE):
            logger.warning(
                "Running PersonDetector in STUB mode — no real detections."
            )
            self._stub_mode = True
            return

        try:
            self._model = YOLO(self.model_name)
            self._model.to(self.device)
            # Warmup with a blank frame
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._model(dummy, verbose=False)
            logger.info(
                "PersonDetector loaded: model=%s device=%s",
                self.model_name,
                self.device,
            )
        except Exception as exc:
            logger.error("Failed to load model %s: %s — using stub", self.model_name, exc)
            self._stub_mode = True
            self._model = None

    # ── Inference ─────────────────────────────────────────────────────────────

    def detect(
        self,
        frame: np.ndarray,
        frame_idx: int = 0,
        timestamp: float = 0.0,
    ) -> List[Detection]:
        """Run inference on a single BGR frame and return person detections."""
        if self._stub_mode or self._model is None:
            return []

        try:
            results = self._model(
                frame,
                conf=self.confidence_threshold,
                classes=[self.PERSON_CLASS_ID],
                verbose=False,
            )
        except Exception as exc:
            logger.error("Inference error: %s", exc)
            return []

        detections: List[Detection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                if cls_id != self.PERSON_CLASS_ID:
                    continue
                conf = float(box.conf[0].item())
                xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                detections.append(
                    Detection(
                        bbox=xyxy,
                        confidence=conf,
                        class_id=cls_id,
                        frame_idx=frame_idx,
                        timestamp=timestamp,
                    )
                )
        return detections

    # ── Benchmark ─────────────────────────────────────────────────────────────

    @classmethod
    def benchmark(
        cls,
        video_path: str,
        n_frames: int = 100,
        models: Optional[List[str]] = None,
        device: str = "cpu",
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """Compute inference FPS and average detection count for a list of models.

        Returns a dict keyed by model name with keys:
            fps, avg_detections, total_frames, elapsed_seconds.
        Used to populate CHOICES.md model selection rationale.
        """
        if models is None:
            models = ["yolo11n.pt", "rtdetr-l.pt"]

        if not _CV2_AVAILABLE:
            return {m: {"fps": 0, "avg_detections": 0, "error": "cv2 unavailable"} for m in models}

        import cv2  # noqa: PLC0415

        results: dict = {}
        for model_name in models:
            if progress_cb:
                progress_cb(f"Benchmarking {model_name}…")
            try:
                detector = cls(model_name=model_name, confidence=0.4, device=device)
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    results[model_name] = {"error": f"Cannot open {video_path}"}
                    continue

                total_detections = 0
                frames_processed = 0
                t0 = time.perf_counter()

                while frames_processed < n_frames:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    dets = detector.detect(frame, frame_idx=frames_processed)
                    total_detections += len(dets)
                    frames_processed += 1

                elapsed = time.perf_counter() - t0
                cap.release()

                fps = frames_processed / elapsed if elapsed > 0 else 0.0
                avg_det = total_detections / max(frames_processed, 1)
                results[model_name] = {
                    "fps": round(fps, 2),
                    "avg_detections": round(avg_det, 2),
                    "total_frames": frames_processed,
                    "elapsed_seconds": round(elapsed, 2),
                }
            except Exception as exc:
                results[model_name] = {"error": str(exc)}

        return results
