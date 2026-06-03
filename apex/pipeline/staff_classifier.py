"""Confidence-based multi-signal staff classifier.

Signals:
  1. presence_duration (weight 0.30) — staff present many hours
  2. opening_hour_presence (weight 0.125) — present at store open
  3. closing_hour_presence (weight 0.125) — present at store close
  4. zone_repetition_count (weight 0.30) — visits same zone many times
  5. appearance_consistency (weight 0.15) — consistent appearance across visits

Never uses hard thresholds; all signals produce soft probabilities.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class StaffClassification:
    """Result of the staff classifier for one visitor's history."""
    is_staff: bool
    staff_confidence: float   # 0.0–1.0
    staff_reason: str         # human-readable explanation
    signal_scores: dict       # breakdown of individual signal scores


class StaffClassifier:
    """Classifies a visitor as staff or customer based on behavioural signals.

    Parameters mirror the config so they can be overridden per-store.
    """

    WEIGHTS = {
        "presence_duration": 0.30,
        "opening_presence": 0.125,
        "closing_presence": 0.125,
        "zone_repetition": 0.30,
        "appearance_consistency": 0.15,
    }

    def __init__(
        self,
        staff_min_presence_hours: float = 4.0,
        zone_repetition_threshold: int = 8,
        store_open_hour: int = 10,
        store_close_hour: int = 21,
        staff_score_threshold: float = 0.55,
    ) -> None:
        self.staff_min_presence_hours = staff_min_presence_hours
        self.zone_repetition_threshold = zone_repetition_threshold
        self.store_open_hour = store_open_hour
        self.store_close_hour = store_close_hour
        self.staff_score_threshold = staff_score_threshold

    # ── Public API ────────────────────────────────────────────────────────────

    def classify(
        self,
        visitor_history: list,          # List of Event ORM objects or dicts
        zone_visit_counts: dict | None = None,   # {zone_name: count}
        appearance_sims: list | None = None,     # list of float cosine sims
    ) -> StaffClassification:
        """Classify a visitor using all available signals.

        Args:
            visitor_history:   All events for this visitor (ordered by time).
            zone_visit_counts: Optional pre-computed {zone: count} dict.
            appearance_sims:   Optional list of pairwise appearance similarities.

        Returns:
            StaffClassification with is_staff, confidence, reason and breakdown.
        """
        signals: dict = {}

        # ── Signal 1: Presence duration ───────────────────────────────────────
        duration_score = self._score_presence_duration(visitor_history)
        signals["presence_duration"] = duration_score

        # ── Signal 2 & 3: Opening / closing hour presence ─────────────────────
        opening_score, closing_score = self._score_hour_presence(visitor_history)
        signals["opening_presence"] = opening_score
        signals["closing_presence"] = closing_score

        # ── Signal 4: Zone repetition ─────────────────────────────────────────
        rep_score = self._score_zone_repetition(
            visitor_history, zone_visit_counts
        )
        signals["zone_repetition"] = rep_score

        # ── Signal 5: Appearance consistency ──────────────────────────────────
        app_score = self._score_appearance_consistency(appearance_sims)
        signals["appearance_consistency"] = app_score

        # ── Weighted combination ──────────────────────────────────────────────
        combined = sum(
            signals[k] * self.WEIGHTS[k] for k in self.WEIGHTS
        )
        combined = float(min(max(combined, 0.0), 1.0))

        is_staff = combined >= self.staff_score_threshold

        reason = self._build_reason(signals, combined)

        return StaffClassification(
            is_staff=is_staff,
            staff_confidence=round(combined, 4),
            staff_reason=reason,
            signal_scores=signals,
        )

    # ── Signal scorers ────────────────────────────────────────────────────────

    def _score_presence_duration(self, history: list) -> float:
        """Sigmoid mapping of total duration hours → [0, 1]."""
        if not history:
            return 0.0
        timestamps = self._extract_timestamps(history)
        if len(timestamps) < 2:
            return 0.0
        duration_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600.0
        # Sigmoid centred on staff_min_presence_hours
        x = duration_hours - self.staff_min_presence_hours
        score = 1.0 / (1.0 + math.exp(-2.0 * x))
        return float(score)

    def _score_hour_presence(self, history: list) -> tuple[float, float]:
        """Check if first/last events fall within 30 min of open/close."""
        timestamps = self._extract_timestamps(history)
        if not timestamps:
            return 0.0, 0.0

        earliest = min(timestamps)
        latest = max(timestamps)

        # Opening: score 1.0 if arrived ≤ 30 min after open
        open_gap = (earliest.hour * 60 + earliest.minute) - (self.store_open_hour * 60)
        opening_score = float(max(0.0, 1.0 - open_gap / 60.0)) if open_gap >= 0 else 0.0
        opening_score = min(opening_score, 1.0)

        # Closing: score 1.0 if last seen ≤ 30 min before close
        close_time_min = self.store_close_hour * 60
        last_min = latest.hour * 60 + latest.minute
        close_gap = close_time_min - last_min
        closing_score = float(max(0.0, 1.0 - close_gap / 60.0)) if close_gap >= 0 else 0.0
        closing_score = min(closing_score, 1.0)

        return opening_score, closing_score

    def _score_zone_repetition(
        self,
        history: list,
        zone_visit_counts: dict | None,
    ) -> float:
        """Soft score based on maximum zone visit count."""
        if zone_visit_counts:
            max_count = max(zone_visit_counts.values(), default=0)
        else:
            # Estimate from event count (each event ≈ one zone presence)
            max_count = len(history)

        if max_count == 0:
            return 0.0
        # Sigmoid centred on threshold
        x = max_count - self.zone_repetition_threshold
        score = 1.0 / (1.0 + math.exp(-0.5 * x))
        return float(score)

    def _score_appearance_consistency(
        self,
        appearance_sims: list | None,
    ) -> float:
        """Mean appearance similarity across visits. High consistency → staff uniform."""
        if not appearance_sims:
            return 0.5   # neutral when no data
        mean_sim = sum(appearance_sims) / len(appearance_sims)
        # High similarity (uniform) → staff. Low similarity → customer.
        return float(min(max(mean_sim, 0.0), 1.0))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_timestamps(history: list) -> list:
        timestamps = []
        for event in history:
            try:
                if hasattr(event, "timestamp"):
                    ts = event.timestamp
                elif isinstance(event, dict):
                    ts = event.get("timestamp")
                else:
                    continue
                if isinstance(ts, datetime):
                    timestamps.append(ts)
            except Exception:
                pass
        return timestamps

    def _build_reason(self, signals: dict, combined: float) -> str:
        parts = []
        for key, score in signals.items():
            label = key.replace("_", " ").title()
            parts.append(f"{label}: {score:.2f}")
        verdict = "STAFF" if combined >= self.staff_score_threshold else "CUSTOMER"
        return (
            f"Classification: {verdict} (combined_score={combined:.3f}) | "
            + " | ".join(parts)
        )
