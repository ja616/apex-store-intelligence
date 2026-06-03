"""Pytest fixtures for APEX Store Intelligence test suite."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Generator, List
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apex.models.database import Base, get_db
from apex.models.events import Event, EventType
from apex.models.sessions import Session as SessionModel, ZoneVisit
from apex.models.transactions import Transaction
from apex.models.visitors import Visitor
from apex.video_processor import ProcessingResult

# ── In-memory SQLite engine ───────────────────────────────────────────────────
from sqlalchemy.pool import StaticPool

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite engine per test function."""
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Yield a scoped DB session for each test."""
    TestSessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ── Sample data ───────────────────────────────────────────────────────────────

STORE_ID = "brigade-road-bangalore"
BASE_TIME = datetime(2026, 4, 10, 12, 0, 0)


def _make_event(
    camera_id: str,
    visitor_id: str,
    event_type: str = EventType.PERSON_DETECTED.value,
    offset_seconds: float = 0,
    confidence: float = 0.85,
    identity_confidence: float = 0.80,
    is_staff: bool = False,
    session_id: str | None = None,
) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        store_id=STORE_ID,
        camera_id=camera_id,
        visitor_id=visitor_id,
        session_id=session_id,
        event_type=event_type,
        timestamp=BASE_TIME + timedelta(seconds=offset_seconds),
        confidence=confidence,
        identity_confidence=identity_confidence,
        is_staff=is_staff,
        bbox_x=10.0,
        bbox_y=20.0,
        bbox_w=50.0,
        bbox_h=100.0,
        schema_version=1,
    )


@pytest.fixture
def sample_visitors() -> List[str]:
    """Return 5 distinct visitor UUIDs."""
    return [str(uuid.uuid4()) for _ in range(5)]


@pytest.fixture
def sample_events(sample_visitors) -> List[Event]:
    """20 realistic events across 5 cameras for 5 visitors."""
    v = sample_visitors
    events = [
        # Visitor 0: entry → floor_a → billing → exit
        _make_event("CAM1", v[0], EventType.PERSON_ENTERED.value, 0),
        _make_event("CAM1", v[0], EventType.PERSON_DETECTED.value, 30),
        _make_event("CAM2", v[0], EventType.ZONE_TRANSITION.value, 60),
        _make_event("CAM2", v[0], EventType.PERSON_DETECTED.value, 120),
        _make_event("CAM4", v[0], EventType.BILLING_ZONE_ENTERED.value, 200),
        _make_event("CAM4", v[0], EventType.BILLING_ZONE_EXITED.value, 300),
        _make_event("CAM1", v[0], EventType.PERSON_EXITED.value, 350),

        # Visitor 1: entry → floor_b only
        _make_event("CAM1", v[1], EventType.PERSON_ENTERED.value, 10),
        _make_event("CAM3", v[1], EventType.PERSON_DETECTED.value, 100),
        _make_event("CAM3", v[1], EventType.PERSON_DETECTED.value, 200),

        # Visitor 2: staff - present all day
        _make_event("CAM2", v[2], EventType.PERSON_DETECTED.value, 0, is_staff=True),
        _make_event("CAM3", v[2], EventType.PERSON_DETECTED.value, 3600, is_staff=True),
        _make_event("CAM2", v[2], EventType.PERSON_DETECTED.value, 7200, is_staff=True),

        # Visitor 3: entry → billing (quick purchase)
        _make_event("CAM1", v[3], EventType.PERSON_ENTERED.value, 500),
        _make_event("CAM4", v[3], EventType.BILLING_ZONE_ENTERED.value, 600),
        _make_event("CAM4", v[3], EventType.BILLING_ZONE_EXITED.value, 700),

        # Visitor 4: re-entry (two separate sessions)
        _make_event("CAM1", v[4], EventType.PERSON_ENTERED.value, 100),
        _make_event("CAM2", v[4], EventType.PERSON_DETECTED.value, 200),
        _make_event("CAM1", v[4], EventType.PERSON_EXITED.value, 400),
        _make_event("CAM1", v[4], EventType.REENTRY_DETECTED.value, 2000),  # long gap
    ]
    return events


@pytest.fixture
def sample_visitor(sample_visitors) -> Visitor:
    return Visitor(
        visitor_id=sample_visitors[0],
        store_id=STORE_ID,
        first_seen=BASE_TIME,
        last_seen=BASE_TIME + timedelta(minutes=30),
        is_staff=False,
        staff_confidence=0.1,
        total_visits=1,
        identity_confidence=0.85,
    )


@pytest.fixture
def sample_session(sample_visitors) -> SessionModel:
    sid = str(uuid.uuid4())
    zv1 = ZoneVisit(
        session_id=sid,
        camera_id="CAM1",
        zone_name="entry",
        entry_time=BASE_TIME,
        exit_time=BASE_TIME + timedelta(seconds=60),
        dwell_seconds=60.0,
        confidence=0.85,
    )
    zv2 = ZoneVisit(
        session_id=sid,
        camera_id="CAM4",
        zone_name="billing",
        entry_time=BASE_TIME + timedelta(seconds=200),
        exit_time=BASE_TIME + timedelta(seconds=300),
        dwell_seconds=100.0,
        confidence=0.80,
    )
    sess = SessionModel(
        session_id=sid,
        visitor_id=sample_visitors[0],
        store_id=STORE_ID,
        entry_time=BASE_TIME,
        exit_time=BASE_TIME + timedelta(seconds=350),
        duration_seconds=350.0,
        converted=False,
        session_confidence=0.82,
        reentry_count=0,
        is_staff=False,
        zones_visited=["entry", "billing"],
    )
    sess.zone_visits = [zv1, zv2]
    return sess


@pytest.fixture
def sample_transactions(sample_visitors) -> List[Transaction]:
    txns = []
    for i in range(5):
        txns.append(Transaction(
            transaction_id=f"ML0426KAP000{1300 + i}_{i}",
            store_id=STORE_ID,
            timestamp=BASE_TIME + timedelta(seconds=310 + i * 100),
            amount=500.0 + i * 100,
            nmv=400.0 + i * 100,
            qty=1,
            customer_name=f"Customer {i}",
            customer_number=f"9{i:09d}",
            is_attributed=False,
        ))
    return txns


@pytest.fixture
def mock_video_processor():
    """Mock VideoProcessor that returns realistic ProcessingResult."""
    mock = MagicMock()
    mock.process_video.return_value = ProcessingResult(
        events_generated=120,
        visitors_detected=8,
        processing_time_seconds=5.2,
        fps=23.1,
        model_used="yolo11n.pt",
        camera_id="CAM1",
        video_path="CAM 1.mp4",
        error=None,
    )
    return mock


@pytest.fixture
def client(db_session):
    """FastAPI test client with DB dependency override."""
    from apex.api.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
