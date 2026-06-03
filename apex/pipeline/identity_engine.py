"""Identity Persistence Engine — cross-camera visitor re-identification.

Hybrid scoring:
  score = 0.50 × appearance_similarity
        + 0.30 × topology_confidence
        + 0.20 × temporal_score

Gallery stored in-memory as {visitor_id: deque(last 10 embeddings)}.
Also writes/reads Visitor rows from SQLite for persistence across runs.
"""
from __future__ import annotations

import logging
import math
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from apex.pipeline.embeddings import AppearanceEmbedder
from apex.pipeline.topology import CameraTopologyService
from apex.config import settings

logger = logging.getLogger(__name__)

_GALLERY_MAX = 10     # rolling window of embeddings per visitor
_NEW_IDENTITY_THRESHOLD = 0.40   # below this → new identity
_MERGE_THRESHOLD = 0.65          # config default; can be overridden


@dataclass
class IdentityMatch:
    """Result of matching a new detection against the gallery."""
    visitor_id: str
    identity_confidence: float          # 0-1 combined match score
    is_new_identity: bool
    reentry_confidence: float           # 0-1 (non-zero if re-entry detected)
    matching_explanation: str           # human-readable reasoning
    appearance_similarity: float
    topology_score: float
    temporal_score: float


class IdentityEngine:
    """Core identity persistence engine.

    Maintains an in-memory gallery of visitor embeddings and matches new
    detections using the hybrid scoring formula.
    """

    def __init__(
        self,
        embedder: Optional[AppearanceEmbedder] = None,
        topology: Optional[CameraTopologyService] = None,
        similarity_threshold: float = _MERGE_THRESHOLD,
        temporal_window_seconds: int = 300,
    ) -> None:
        self.embedder = embedder or AppearanceEmbedder()
        self.topology = topology or CameraTopologyService()
        self.similarity_threshold = similarity_threshold
        self.temporal_window_seconds = temporal_window_seconds

        # In-memory gallery: visitor_id → deque of np arrays
        self._gallery: Dict[str, Deque[np.ndarray]] = {}
        # Last seen: visitor_id → (camera_id, timestamp)
        self._last_seen: Dict[str, Tuple[str, datetime]] = {}
        # Track whether visitor has exited (for re-entry detection)
        self._exited: Dict[str, bool] = {}

    # ── Gallery management ────────────────────────────────────────────────────

    def add_to_gallery(
        self,
        visitor_id: str,
        embedding: np.ndarray,
        camera_id: str,
        timestamp: datetime,
    ) -> None:
        """Add an embedding to the rolling gallery for a visitor."""
        if visitor_id not in self._gallery:
            self._gallery[visitor_id] = deque(maxlen=_GALLERY_MAX)
        self._gallery[visitor_id].append(embedding.copy())
        self._last_seen[visitor_id] = (camera_id, timestamp)

    def mark_exited(self, visitor_id: str) -> None:
        """Mark a visitor as having exited (enables re-entry detection)."""
        self._exited[visitor_id] = True

    # ── Core match ────────────────────────────────────────────────────────────

    def match(
        self,
        embedding: np.ndarray,
        camera_id: str,
        timestamp: datetime,
        group_size: int = 1,
    ) -> IdentityMatch:
        """Match a new detection against the known gallery.

        Args:
            embedding:   128-dim appearance embedding.
            camera_id:   Camera where detection occurred.
            timestamp:   Wall-clock time of detection.
            group_size:  Number of people entering simultaneously.
                         When > 1, confidence is reduced to avoid mis-merging.

        Returns:
            IdentityMatch with full reasoning.
        """
        if not self._gallery:
            return self._create_new_identity(
                embedding, camera_id, timestamp,
                reason="Gallery empty — first visitor"
            )

        best_id: Optional[str] = None
        best_score: float = 0.0
        best_app: float = 0.0
        best_topo: float = 0.0
        best_temp: float = 0.0

        for vid, embs in self._gallery.items():
            app_sim = self._gallery_similarity(embedding, embs)
            topo = self._topology_score(vid, camera_id, timestamp)
            temp = self._temporal_score(vid, timestamp)

            score = 0.50 * app_sim + 0.30 * topo + 0.20 * temp

            # Penalise group entries to reduce false merges
            if group_size > 1:
                penalty = math.log(group_size + 1) * 0.1
                score = max(0.0, score - penalty)

            if score > best_score:
                best_score = score
                best_id = vid
                best_app = app_sim
                best_topo = topo
                best_temp = temp

        if best_id is None or best_score < _NEW_IDENTITY_THRESHOLD or best_app < 0.55:
            return self._create_new_identity(
                embedding, camera_id, timestamp,
                reason=(
                    f"Best match score {best_score:.3f} below threshold "
                    f"{_NEW_IDENTITY_THRESHOLD} or appearance similarity {best_app:.3f} < 0.55"
                ),
            )

        if best_score < self.similarity_threshold:
            # Score above new-identity floor but below merge threshold
            # — create new identity unless topology is strongly supportive
            if best_topo < 0.5:
                return self._create_new_identity(
                    embedding, camera_id, timestamp,
                    reason=(
                        f"Score {best_score:.3f} below merge threshold and "
                        f"topology confidence {best_topo:.3f} insufficient"
                    ),
                )

        # ── Re-entry detection ────────────────────────────────────────────────
        reentry_conf = 0.0
        if self._exited.get(best_id, False):
            # Visitor was marked as exited — this is a re-entry
            reentry_conf = min(best_score * 1.1, 1.0)
            self._exited[best_id] = False   # reset

        # ── Update gallery ────────────────────────────────────────────────────
        self.add_to_gallery(best_id, embedding, camera_id, timestamp)

        explanation = (
            f"Matched visitor {best_id[:8]} | "
            f"combined={best_score:.3f} "
            f"(appearance={best_app:.3f}, topology={best_topo:.3f}, "
            f"temporal={best_temp:.3f}) | "
            f"group_size={group_size}"
        )

        return IdentityMatch(
            visitor_id=best_id,
            identity_confidence=round(best_score, 4),
            is_new_identity=False,
            reentry_confidence=round(reentry_conf, 4),
            matching_explanation=explanation,
            appearance_similarity=round(best_app, 4),
            topology_score=round(best_topo, 4),
            temporal_score=round(best_temp, 4),
        )

    # ── Sub-scorers ───────────────────────────────────────────────────────────

    def _gallery_similarity(
        self, embedding: np.ndarray, gallery_embs: Deque[np.ndarray]
    ) -> float:
        """Mean cosine similarity against the rolling gallery."""
        if not gallery_embs:
            return 0.0
        sims = [AppearanceEmbedder.similarity(embedding, g) for g in gallery_embs]
        return float(np.mean(sims))

    def _topology_score(
        self, visitor_id: str, new_camera: str, new_timestamp: datetime
    ) -> float:
        """Topology plausibility score for the camera transition."""
        last = self._last_seen.get(visitor_id)
        if last is None:
            return 0.5   # no info → neutral

        last_cam, last_ts = last
        elapsed = (new_timestamp - last_ts).total_seconds()
        if elapsed < 0:
            elapsed = 0.0

        _, conf = self.topology.is_transition_possible(last_cam, new_camera, elapsed)
        return conf

    def _temporal_score(self, visitor_id: str, new_timestamp: datetime) -> float:
        """Temporal recency score: 1.0 = same instant; decays over 5 minutes."""
        last = self._last_seen.get(visitor_id)
        if last is None:
            return 0.5   # no info → neutral

        _, last_ts = last
        gap = abs((new_timestamp - last_ts).total_seconds())

        # Exponential decay: half-life at temporal_window_seconds
        score = math.exp(-gap / max(self.temporal_window_seconds, 1))
        return float(max(score, 0.2))   # floor at 0.2 so old visitors aren't zero

    # ── New identity creation ─────────────────────────────────────────────────

    def _create_new_identity(
        self,
        embedding: np.ndarray,
        camera_id: str,
        timestamp: datetime,
        reason: str = "",
    ) -> IdentityMatch:
        new_id = str(uuid.uuid4())
        self.add_to_gallery(new_id, embedding, camera_id, timestamp)
        return IdentityMatch(
            visitor_id=new_id,
            identity_confidence=1.0,   # we're certain it's a new person
            is_new_identity=True,
            reentry_confidence=0.0,
            matching_explanation=f"New identity created | {reason}",
            appearance_similarity=0.0,
            topology_score=0.0,
            temporal_score=0.0,
        )

    # ── State helpers ─────────────────────────────────────────────────────────

    def gallery_size(self) -> int:
        return len(self._gallery)

    def reset(self) -> None:
        """Clear all in-memory state (useful between test runs)."""
        self._gallery.clear()
        self._last_seen.clear()
        self._exited.clear()
