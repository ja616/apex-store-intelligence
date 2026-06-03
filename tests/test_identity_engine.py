"""Tests for IdentityEngine — cross-camera visitor re-identification."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import numpy as np
import pytest

from apex.pipeline.identity_engine import IdentityEngine, IdentityMatch
from apex.pipeline.topology import CameraTopologyService


@pytest.fixture
def engine():
    """Fresh IdentityEngine per test."""
    topo = CameraTopologyService()
    return IdentityEngine(topology=topo, similarity_threshold=0.65, temporal_window_seconds=300)


def _make_embedding(seed: int = 0, noise: float = 0.0) -> np.ndarray:
    """Reproducible 128-dim L2-normalised embedding with optional noise."""
    rng = np.random.default_rng(seed)
    vec = rng.normal(0, 1, 128).astype(np.float32)
    if noise > 0:
        vec += rng.normal(0, noise, 128).astype(np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 1e-8 else vec


BASE_TIME = datetime(2026, 4, 10, 12, 0, 0)


class TestSamePersonDifferentCamera:
    """Same person seen in different cameras should be merged."""

    def test_merge_with_valid_topology(self, engine):
        emb = _make_embedding(seed=1)
        noisy_emb = _make_embedding(seed=1, noise=0.05)   # very similar

        # First detection at CAM1
        match1 = engine.match(emb, "CAM1", BASE_TIME)
        assert match1.is_new_identity

        # Same person at CAM2 two minutes later (valid transition CAM1→CAM2)
        match2 = engine.match(noisy_emb, "CAM2", BASE_TIME + timedelta(seconds=90))

        assert not match2.is_new_identity, "Should recognise same person across cameras"
        assert match2.visitor_id == match1.visitor_id
        assert match2.identity_confidence >= 0.5
        assert match2.appearance_similarity >= 0.0


class TestDifferentPeopleTopologyPrevents:
    """Two different people with superficially similar appearance in impossible transition."""

    def test_impossible_transition_reduces_confidence(self, engine):
        emb_a = _make_embedding(seed=10, noise=0.02)
        emb_b = _make_embedding(seed=10, noise=0.03)   # very similar appearance

        # Person A at CAM1
        match_a = engine.match(emb_a, "CAM1", BASE_TIME)
        assert match_a.is_new_identity

        # Person B at CAM4 3 seconds later — impossible (CAM1→CAM4 min 30s)
        match_b = engine.match(emb_b, "CAM4", BASE_TIME + timedelta(seconds=3))

        # Topology penalty should reduce confidence below merge threshold
        # or create a new identity
        if not match_b.is_new_identity:
            # If merged, topology score should be low
            assert match_b.topology_score < 0.5, (
                "Topology should heavily penalise 3s CAM1→CAM4 transition"
            )


class TestReentryDetection:
    """Re-entry after 10 minutes should be detected."""

    def test_reentry_after_10_minutes(self, engine):
        emb = _make_embedding(seed=42)

        # First visit
        match1 = engine.match(emb, "CAM1", BASE_TIME)
        vid = match1.visitor_id

        # Mark as exited
        engine.mark_exited(vid)

        # Re-entry 10 minutes later
        match2 = engine.match(emb, "CAM1", BASE_TIME + timedelta(minutes=10))

        assert not match2.is_new_identity, "Should recognise returning visitor"
        assert match2.visitor_id == vid
        assert match2.reentry_confidence > 0.7, (
            f"Re-entry confidence should be > 0.7 but got {match2.reentry_confidence}"
        )


class TestImpossibleTopology:
    """Impossible topology transition reduces identity confidence."""

    def test_identity_confidence_reduced_for_impossible_transition(self, engine):
        emb = _make_embedding(seed=7)

        # Register at CAM4
        match1 = engine.match(emb, "CAM4", BASE_TIME)
        vid = match1.visitor_id

        # Claim same person at CAM1 1 second later — physically impossible
        match2 = engine.match(emb, "CAM1", BASE_TIME + timedelta(seconds=1))

        # Either new identity OR low topology score
        if not match2.is_new_identity:
            assert match2.topology_score < 0.5, (
                "Topology score should be low for 1s CAM4→CAM1 transition"
            )


class TestGroupEntry:
    """3 people entering simultaneously should get distinct identities."""

    def test_group_entry_creates_distinct_identities(self, engine):
        ts = BASE_TIME
        ids = set()

        for i in range(3):
            emb = _make_embedding(seed=100 + i)   # distinct people
            match = engine.match(emb, "CAM1", ts, group_size=3)
            ids.add(match.visitor_id)

        assert len(ids) == 3, f"Expected 3 distinct identities, got {len(ids)}"


class TestGalleryManagement:
    """Gallery should grow and support similarity queries."""

    def test_gallery_grows_on_new_identities(self, engine):
        for i in range(5):
            emb = _make_embedding(seed=200 + i * 10)   # distinct seeds → distinct people
            engine.match(emb, "CAM1", BASE_TIME + timedelta(seconds=i))

        assert engine.gallery_size() == 5

    def test_reset_clears_gallery(self, engine):
        emb = _make_embedding(seed=99)
        engine.match(emb, "CAM1", BASE_TIME)
        engine.reset()
        assert engine.gallery_size() == 0
