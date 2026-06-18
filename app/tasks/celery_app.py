"""Celery application instance and beat schedule."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "tvai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_max_tasks_per_child=20,  # recycle workers (Playwright leaks)
)

# Beat dispatches the scheduler every minute; the scheduler decides which
# user schedules are due. This keeps a single source of truth in the DB.
celery_app.conf.beat_schedule = {
    "dispatch-due-schedules": {
        "task": "app.tasks.tasks.dispatch_due_schedules",
        "schedule": crontab(minute="*"),
    }
}
