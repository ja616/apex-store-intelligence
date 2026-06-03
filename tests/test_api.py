"""Tests for all API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from tests.conftest import STORE_ID, BASE_TIME


class TestHealthEndpoint:
    """GET /api/v1/health"""

    def test_health_returns_200(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_has_required_fields(self, client):
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert "status" in data
        assert "db_status" in data
        assert "confidence" in data
        assert "latency_ms" in data
        assert "timestamp" in data

    def test_health_db_ok(self, client):
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert data["db_status"] == "ok"


class TestEventIngestion:
    """POST /api/v1/events/ingest"""

    def _make_event_payload(self, event_id: str | None = None) -> dict:
        return {
            "event_id": event_id or str(uuid.uuid4()),
            "store_id": STORE_ID,
            "camera_id": "CAM1",
            "visitor_id": str(uuid.uuid4()),
            "event_type": "PERSON_DETECTED",
            "timestamp": BASE_TIME.isoformat(),
            "confidence": 0.85,
            "identity_confidence": 0.80,
            "is_staff": False,
            "schema_version": 1,
        }

    def test_ingest_single_event(self, client):
        payload = {"events": [self._make_event_payload()]}
        resp = client.post("/api/v1/events/ingest", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] == 1
        assert data["skipped_duplicates"] == 0
        assert data["confidence_avg"] == pytest.approx(0.85, rel=1e-3)

    def test_ingest_multiple_events(self, client):
        events = [self._make_event_payload() for _ in range(5)]
        resp = client.post("/api/v1/events/ingest", json={"events": events})
        assert resp.status_code == 200
        assert resp.json()["accepted"] == 5

    def test_idempotency_duplicate_skipped(self, client):
        event_id = str(uuid.uuid4())
        payload = {"events": [self._make_event_payload(event_id)]}

        resp1 = client.post("/api/v1/events/ingest", json=payload)
        assert resp1.json()["accepted"] == 1

        resp2 = client.post("/api/v1/events/ingest", json=payload)
        data2 = resp2.json()
        assert data2["accepted"] == 0
        assert data2["skipped_duplicates"] == 1

    def test_validation_error_on_bad_confidence(self, client):
        event = self._make_event_payload()
        event["confidence"] = 1.5   # > 1.0 — invalid
        resp = client.post("/api/v1/events/ingest", json={"events": [event]})
        assert resp.status_code == 422   # Unprocessable Entity


class TestStoreMetrics:
    """GET /api/v1/stores/{store_id}/metrics"""

    def test_empty_store_returns_valid_metrics(self, client):
        resp = client.get(f"/api/v1/stores/{STORE_ID}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unique_visitors"] == 0
        assert data["conversion_rate"] == 0.0
        assert "metric_confidence" in data
        assert "reasoning" in data

    def test_metrics_include_confidence(self, client, db_session, sample_session):
        from apex.models.sessions import Session as SessionModel
        db_session.add(sample_session)
        db_session.commit()

        resp = client.get(f"/api/v1/stores/{STORE_ID}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metric_confidence" in data
        assert 0.0 <= data["metric_confidence"] <= 1.0


class TestStoreFunnel:
    """GET /api/v1/stores/{store_id}/funnel"""

    def test_funnel_returns_stages(self, client):
        resp = client.get(f"/api/v1/stores/{STORE_ID}/funnel")
        assert resp.status_code == 200
        data = resp.json()
        assert "stages" in data
        assert len(data["stages"]) == 4   # entered, browsed, billing_zone, purchased

    def test_funnel_stage_names(self, client):
        resp = client.get(f"/api/v1/stores/{STORE_ID}/funnel")
        stage_names = [s["stage"] for s in resp.json()["stages"]]
        assert "entered" in stage_names
        assert "purchased" in stage_names

    def test_funnel_has_confidence(self, client):
        resp = client.get(f"/api/v1/stores/{STORE_ID}/funnel")
        data = resp.json()
        assert "metric_confidence" in data
        for stage in data["stages"]:
            assert "confidence" in stage


class TestStoreHeatmap:
    """GET /api/v1/stores/{store_id}/heatmap"""

    def test_heatmap_returns_200(self, client):
        resp = client.get(f"/api/v1/stores/{STORE_ID}/heatmap")
        assert resp.status_code == 200

    def test_heatmap_has_confidence(self, client):
        resp = client.get(f"/api/v1/stores/{STORE_ID}/heatmap")
        data = resp.json()
        assert "metric_confidence" in data
        assert "zones" in data


class TestStoreAnomalies:
    """GET /api/v1/stores/{store_id}/anomalies"""

    def test_anomalies_returns_200(self, client):
        resp = client.get(f"/api/v1/stores/{STORE_ID}/anomalies")
        assert resp.status_code == 200

    def test_anomalies_response_structure(self, client):
        resp = client.get(f"/api/v1/stores/{STORE_ID}/anomalies")
        data = resp.json()
        assert "anomalies" in data
        assert "total" in data
        assert isinstance(data["anomalies"], list)


class TestRootEndpoint:
    def test_root_returns_service_info(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "service" in data
        assert "APEX" in data["service"]
