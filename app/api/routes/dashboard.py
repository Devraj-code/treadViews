"""Dashboard summary route + screenshot serving."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import AnalysisJob, JobStatus, Report, Schedule, TradingViewSnapshot, User, Watchlist
from app.schemas.trading import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = current_user.id

    def _count(model, *filters):
        return db.query(func.count(model.id)).filter(*filters).scalar() or 0

    recent = (
        db.query(Report)
        .filter(Report.user_id == uid)
        .order_by(Report.created_at.desc())
        .limit(5)
        .all()
    )
    return DashboardSummary(
        total_jobs=_count(AnalysisJob, AnalysisJob.user_id == uid),
        completed_jobs=_count(AnalysisJob, AnalysisJob.user_id == uid, AnalysisJob.status == JobStatus.completed),
        failed_jobs=_count(AnalysisJob, AnalysisJob.user_id == uid, AnalysisJob.status == JobStatus.failed),
        total_reports=_count(Report, Report.user_id == uid),
        active_schedules=_count(Schedule, Schedule.user_id == uid, Schedule.is_active.is_(True)),
        watchlist_count=_count(Watchlist, Watchlist.user_id == uid),
        recent_reports=recent,
    )


@router.get("/snapshot/{job_id}/image")
def snapshot_image(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(AnalysisJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    snap = db.query(TradingViewSnapshot).filter(TradingViewSnapshot.job_id == job_id).first()
    if not snap or not snap.screenshot_path or not os.path.exists(snap.screenshot_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Screenshot not available")
    # Path-traversal guard: ensure file lives under the configured screenshot dir.
    base = os.path.realpath(settings.SCREENSHOT_DIR)
    if not os.path.realpath(snap.screenshot_path).startswith(base):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return FileResponse(snap.screenshot_path, media_type="image/png")
