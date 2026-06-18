"""Report routes: list/filter reports and download PDF."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Report, User
from app.schemas.trading import ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportOut])
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    symbol: str | None = None,
    trend: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=100),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    q = db.query(Report).filter(Report.user_id == current_user.id)
    if symbol:
        q = q.filter(Report.symbol == symbol.upper())
    if trend:
        q = q.filter(Report.trend == trend)
    if min_confidence is not None:
        q = q.filter(Report.confidence >= min_confidence)
    return q.order_by(Report.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report or report.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report


@router.get("/{report_id}/pdf")
def download_pdf(report_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report or report.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if not report.pdf_path or not os.path.exists(report.pdf_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF not available")
    filename = f"{report.symbol}_{report.timeframe}_report.pdf"
    return FileResponse(report.pdf_path, media_type="application/pdf", filename=filename)
