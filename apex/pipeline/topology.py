"""Camera topology service — graph of possible transitions between cameras.

Loads from configs/store_topology.json and answers:
  - Is a transition from CAM-A to CAM-B in N seconds physically plausible?
  - What is the confidence score for that transition?
  - What is the shortest path between two cameras?
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Optional networkx for shortest-path computation
try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False
    logger.warning("networkx not available — topology shortest-path disabled")


class CameraTopologyService:
    """Loads and queries the store camera graph."""

    def __init__(self, config_path: str = "configs/store_topology.json") -> None:
        self._config: dict = {}
        self._transitions: Dict[Tuple[str, str], dict] = {}
        self._impossible: List[dict] = []
        self._cameras: Dict[str, dict] = {}
        self._graph = None
        self._load(config_path)

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load(self, config_path: str) -> None:
        path = Path(config_path)
        if not path.exists():
            # Try relative to project root
            alt = Path(__file__).parent.parent.parent / config_path
            if alt.exists():
                path = alt
        if not path.exists():
            logger.warning("Topology config not found at %s — using defaults", config_path)
            self._load_defaults()
            return
        try:
            with open(path, encoding="utf-8") as f:
                self._config = json.load(f)
            self._parse()
            logger.info("Topology loaded from %s", path)
        except Exception as exc:
            logger.error("Failed to load topology: %s", exc)
            self._load_defaults()

    def _load_defaults(self) -> None:
        """Minimal fallback topology (linear: CAM1→CAM2→CAM3→CAM4↔CAM5)."""
        self._config = {
            "cameras": {
                "CAM1": {"name": "Entry Gate", "zone": "entry"},
                "CAM2": {"name": "Floor Zone A", "zone": "floor_a"},
                "CAM3": {"name": "Floor Zone B", "zone": "floor_b"},
                "CAM4": {"name": "Billing Counter A", "zone": "billing"},
                "CAM5": {"name": "Billing Counter B", "zone": "billing"},
            },
            "transitions": [
                {"from": "CAM1", "to": "CAM2", "min_seconds": 5, "max_seconds": 120},
                {"from": "CAM2", "to": "CAM1", "min_seconds": 5, "max_seconds": 120},
                {"from": "CAM2", "to": "CAM3", "min_seconds": 10, "max_seconds": 180},
                {"from": "CAM3", "to": "CAM2", "min_seconds": 10, "max_seconds": 180},
                {"from": "CAM3", "to": "CAM4", "min_seconds": 10, "max_seconds": 120},
                {"from": "CAM3", "to": "CAM5", "min_seconds": 10, "max_seconds": 120},
                {"from": "CAM4", "to": "CAM5", "min_seconds": 5, "max_seconds": 60},
                {"from": "CAM5", "to": "CAM4", "min_seconds": 5, "max_seconds": 60},
            ],
            "impossible_transitions": [],
        }
        self._parse()

    def _parse(self) -> None:
        self._cameras = self._config.get("cameras", {})
        for t in self._config.get("transitions", []):
            key = (t["from"], t["to"])
            self._transitions[key] = t
        self._impossible = self._config.get("impossible_transitions", [])

        if _NX_AVAILABLE:
            self._graph = nx.DiGraph()
            for cam_id in self._cameras:
                self._graph.add_node(cam_id)
            for t in self._config.get("transitions", []):
                # Edge weight = midpoint of expected travel time
                mid = (t["min_seconds"] + t["max_seconds"]) / 2
                self._graph.add_edge(t["from"], t["to"], weight=mid)

    # ── Core queries ──────────────────────────────────────────────────────────

    def is_transition_possible(
        self,
        from_cam: str,
        to_cam: str,
        elapsed_seconds: float,
    ) -> Tuple[bool, float]:
        """Check whether a camera-to-camera transition is physically plausible.

        Returns (possible: bool, confidence: float).
        Confidence degrades smoothly — never a hard binary cut.
        """
        if from_cam == to_cam:
            # Same camera re-detection: always possible, very high confidence
            return True, 0.95

        # Check impossible transitions first
        for imp in self._impossible:
            if imp["from"] == from_cam and imp["to"] == to_cam:
                if elapsed_seconds <= imp.get("max_seconds", 0):
                    # Physically impossible (e.g., teleportation)
                    return False, 0.05

        key = (from_cam, to_cam)
        t = self._transitions.get(key)
        if t is None:
            # Unknown transition — conservatively low but not zero
            return True, 0.3

        conf = self.get_transition_confidence(from_cam, to_cam, elapsed_seconds)
        return conf > 0.1, conf

    def get_transition_confidence(
        self,
        from_cam: str,
        to_cam: str,
        elapsed_seconds: float,
    ) -> float:
        """Soft confidence score for a camera-to-camera transition.

        Returns 1.0 for perfectly timed transitions; decays toward 0.0
        for physically implausible ones.
        """
        if from_cam == to_cam:
            return 0.95

        key = (from_cam, to_cam)
        t = self._transitions.get(key)
        if t is None:
            return 0.3   # unknown edge

        t_min: float = t["min_seconds"]
        t_max: float = t["max_seconds"]

        if elapsed_seconds < t_min:
            # Arrived too fast — exponential decay
            deficit = t_min - elapsed_seconds
            return float(math.exp(-deficit / max(t_min, 1.0)) * 0.5)

        if elapsed_seconds <= t_max:
            # Within the expected window — linearly interpolated [0.7, 1.0]
            ratio = (elapsed_seconds - t_min) / max(t_max - t_min, 1.0)
            # Peak confidence at midpoint
            mid_ratio = abs(ratio - 0.5) * 2  # 0 at mid, 1 at edges
            return float(1.0 - 0.3 * mid_ratio)

        # Overdue — exponential decay
        surplus = elapsed_seconds - t_max
        return float(math.exp(-surplus / max(t_max, 1.0)) * 0.7)

    def get_path(self, from_cam: str, to_cam: str) -> List[str]:
        """Shortest path between two cameras (by expected travel time)."""
        if not _NX_AVAILABLE or self._graph is None:
            return [from_cam, to_cam]
        try:
            return nx.shortest_path(
                self._graph, source=from_cam, target=to_cam, weight="weight"
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return [from_cam, to_cam]

    def get_zone(self, camera_id: str) -> str:
        """Return the zone name for a given camera ID."""
        return self._cameras.get(camera_id, {}).get("zone", camera_id.lower())

    def get_camera_name(self, camera_id: str) -> str:
        return self._cameras.get(camera_id, {}).get("name", camera_id)

    def all_cameras(self) -> List[str]:
        return list(self._cameras.keys())
