"""Video processing router — accepts video uploads and manages processing jobs."""
from __future__ import annotations

import logging
import os
import tempfile
import threading
import uuid
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session as DBSession

from apex.api.schemas import JobStatusResponse, VideoProcessingResponse
from apex.models.database import get_db
from apex.video_processor import ProcessingResult, VideoProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/process", tags=["processing"])

# In-memory job registry (replace with Redis/DB for production)
_jobs: Dict[str, dict] = {}


def _run_job(job_id: str, video_path: str, camera_id: str, store_id: str, max_frames: int | None) -> None:
    """Background thread: process video and update job registry."""
    _jobs[job_id]["status"] = "running"

    def progress_cb(info: dict) -> None:
        _jobs[job_id]["progress_pct"] = info.get("percent", 0.0)
        _jobs[job_id]["events_generated"] = info.get("events", 0)

    processor = VideoProcessor(progress_cb=progress_cb)

    try:
        result: ProcessingResult = processor.process_video(
            video_path=video_path,
            camera_id=camera_id,
            store_id=store_id,
            max_frames=max_frames,
        )
        _jobs[job_id].update({
            "status": "done" if not result.error else "failed",
            "progress_pct": 100.0,
            "events_generated": result.events_generated,
            "visitors_detected": result.visitors_detected,
            "processing_time_seconds": result.processing_time_seconds,
            "fps": result.fps,
            "model_used": result.model_used,
            "error": result.error,
            "result": {
                "events_generated": result.events_generated,
                "visitors_detected": result.visitors_detected,
                "fps": result.fps,
            },
        })
    except Exception as exc:
        _jobs[job_id].update({"status": "failed", "error": str(exc)})
    finally:
        # Clean up temp file
        try:
            if video_path.startswith(tempfile.gettempdir()):
                os.unlink(video_path)
        except Exception:
            pass


@router.post("/video", response_model=VideoProcessingResponse)
async def process_video(
    file: UploadFile = File(...),
    camera_id: str = Form(...),
    store_id: str = Form(...),
    max_frames: int | None = Form(default=None),
) -> VideoProcessingResponse:
    """Accept a video upload and launch background processing job."""
    job_id = str(uuid.uuid4())

    # Save upload to temp file
    suffix = os.path.splitext(file.filename or "video")[1] or ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"File upload failed: {exc}") from exc

    _jobs[job_id] = {
        "status": "pending",
        "progress_pct": 0.0,
        "events_generated": 0,
        "visitors_detected": 0,
        "processing_time_seconds": 0.0,
        "fps": 0.0,
        "model_used": "",
        "error": None,
        "result": None,
    }

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, tmp.name, camera_id, store_id, max_frames),
        daemon=True,
    )
    thread.start()

    return VideoProcessingResponse(
        job_id=job_id,
        status="pending",
        message=f"Job {job_id} accepted. Poll /api/v1/process/jobs/{job_id} for status.",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    """Get processing job status and result."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress_pct=job["progress_pct"],
        events_generated=job["events_generated"],
        visitors_detected=job["visitors_detected"],
        processing_time_seconds=job["processing_time_seconds"],
        fps=job["fps"],
        model_used=job["model_used"],
        error=job["error"],
        result=job.get("result"),
    )
