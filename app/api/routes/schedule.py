"""Schedule routes: create/list/toggle/delete automated analyses."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Schedule, ScheduleInterval, User
from app.schemas.trading import ScheduleCreate, ScheduleOut

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("", response_model=list[ScheduleOut])
def list_schedules(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Schedule)
        .filter(Schedule.user_id == current_user.id)
        .order_by(Schedule.created_at.desc())
        .all()
    )


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        interval = ScheduleInterval(payload.interval)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"interval must be one of {[i.value for i in ScheduleInterval]}",
        )
    sched = Schedule(
        user_id=current_user.id,
        symbol=payload.symbol.upper(),
        timeframe=payload.timeframe,
        indicators=payload.indicators,
        interval=interval,
        next_run_at=datetime.now(timezone.utc),  # run on the next beat tick
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


@router.patch("/{schedule_id}/toggle", response_model=ScheduleOut)
def toggle_schedule(schedule_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sched = db.get(Schedule, schedule_id)
    if not sched or sched.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schedule not found")
    sched.is_active = not sched.is_active
    db.commit()
    db.refresh(sched)
    return sched


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sched = db.get(Schedule, schedule_id)
    if not sched or sched.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schedule not found")
    db.delete(sched)
    db.commit()
