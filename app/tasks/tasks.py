"""Celery tasks: run a single analysis job and dispatch scheduled jobs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models import AnalysisJob, JobStatus, Schedule, ScheduleInterval
from app.services.analysis import run_job
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_INTERVAL_DELTA = {
    ScheduleInterval.every_5_min: timedelta(minutes=5),
    ScheduleInterval.every_15_min: timedelta(minutes=15),
    ScheduleInterval.hourly: timedelta(hours=1),
    ScheduleInterval.daily: timedelta(days=1),
}


@celery_app.task(name="app.tasks.tasks.run_analysis_job", bind=True, max_retries=2)
def run_analysis_job(self, job_id: str, as_of: str | None = None) -> str:
    try:
        return run_job(job_id, as_of=as_of)
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_analysis_job error for %s", job_id)
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.tasks.tasks.dispatch_due_schedules")
def dispatch_due_schedules() -> int:
    """Find active schedules whose next_run_at is due, enqueue jobs, advance them."""
    now = datetime.now(timezone.utc)
    dispatched = 0
    db = SessionLocal()
    try:
        due = (
            db.query(Schedule)
            .filter(Schedule.is_active.is_(True))
            .filter((Schedule.next_run_at.is_(None)) | (Schedule.next_run_at <= now))
            .all()
        )
        for sched in due:
            job = AnalysisJob(
                user_id=sched.user_id,
                symbol=sched.symbol,
                timeframe=sched.timeframe,
                indicators=sched.indicators,
                status=JobStatus.pending,
            )
            db.add(job)
            db.flush()
            sched.last_run_at = now
            sched.next_run_at = now + _INTERVAL_DELTA[sched.interval]
            db.commit()
            run_analysis_job.delay(job.id)
            dispatched += 1
        logger.info("Dispatched %s scheduled jobs", dispatched)
        return dispatched
    finally:
        db.close()
