"""Analysis routes: trigger jobs, list history, fetch single job + report."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import AnalysisJob, Report, User
from app.schemas.trading import AnalysisJobOut, AnalysisRunRequest, ReportOut
from app.services.audit import record_audit

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _enqueue(job_id: str, as_of: str | None = None) -> None:
    """Enqueue via Celery; fall back to synchronous run if the broker is down."""
    try:
        from app.tasks.tasks import run_analysis_job

        run_analysis_job.delay(job_id, as_of)
    except Exception:  # noqa: BLE001
        from app.services.analysis import run_job

        run_job(job_id, as_of=as_of)


@router.post("/run", response_model=AnalysisJobOut, status_code=status.HTTP_202_ACCEPTED)
def run_analysis(
    payload: AnalysisRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = AnalysisJob(
        user_id=current_user.id,
        symbol=payload.symbol.upper(),
        timeframe=payload.timeframe,
        indicators=payload.indicators,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    record_audit(db, action="analysis.run", user_id=current_user.id, detail=job.symbol)
    _enqueue(job.id, payload.as_of.isoformat() if payload.as_of else None)
    return job


@router.get("/history", response_model=list[AnalysisJobOut])
def history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200),
    offset: int = 0,
    symbol: str | None = None,
):
    q = db.query(AnalysisJob).filter(AnalysisJob.user_id == current_user.id)
    if symbol:
        q = q.filter(AnalysisJob.symbol == symbol.upper())
    return q.order_by(AnalysisJob.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{job_id}", response_model=AnalysisJobOut)
def get_job(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(AnalysisJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.get("/{job_id}/report", response_model=ReportOut)
def get_job_report(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(AnalysisJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    report = db.query(Report).filter(Report.job_id == job_id).first()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not ready")
    return report
