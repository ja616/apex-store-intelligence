"""APEX Store Intelligence — Configuration"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./apex_store.db"

    # ── Store ─────────────────────────────────────────────────────────────────
    store_id: str = "brigade-road-bangalore"
    store_name: str = "Purplle Brigade Road"

    # ── Detection ─────────────────────────────────────────────────────────────
    detector_model: str = "yolo11n.pt"   # ultralytics YOLOv11n
    detector_confidence: float = 0.4
    detector_device: str = "cpu"         # or "cuda"

    # ── Identity / Re-ID ──────────────────────────────────────────────────────
    reid_model: str = "osnet_x0_25"
    reid_similarity_threshold: float = 0.65
    reid_temporal_window_seconds: int = 300   # 5-min max re-entry gap

    # ── Session builder ───────────────────────────────────────────────────────
    session_gap_seconds: int = 60
    billing_zone_cameras: List[str] = ["CAM4", "CAM5"]
    entry_cameras: List[str] = ["CAM1"]

    # ── Staff detection ───────────────────────────────────────────────────────
    staff_min_presence_hours: float = 4.0
    staff_zone_repetition_threshold: int = 8

    # ── Conversion ────────────────────────────────────────────────────────────
    billing_temporal_window_seconds: int = 600   # 10-min POS match window

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # ── Observability ─────────────────────────────────────────────────────────
    enable_prometheus: bool = True
    log_level: str = "INFO"

    # ── Paths ─────────────────────────────────────────────────────────────────
    topology_config: str = "configs/store_topology.json"
    camera_config: str = "configs/camera_config.json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
