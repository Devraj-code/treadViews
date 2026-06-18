"""Orchestrates a single analysis job end-to-end.

Steps: scrape TradingView -> persist snapshot -> run agentic workflow ->
persist agent outputs + report -> render PDF. Designed to run inside a Celery
worker (it opens its own DB session).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.workflow import run_analysis_workflow
from app.core.security import decrypt_secret
from app.db.session import SessionLocal
from app.models import (
    AgentOutput,
    AnalysisJob,
    JobStatus,
    Report,
    TradingViewCredential,
    TradingViewSnapshot,
)
from app.playwright.tradingview_scraper import TradingViewScraper
from app.reports.pdf_generator import generate_pdf
from app.services.audit import record_audit

logger = logging.getLogger(__name__)


def _resolve_tv_credentials(db: Session, user_id: str) -> tuple[str | None, str | None]:
    cred = (
        db.query(TradingViewCredential)
        .filter(TradingViewCredential.user_id == user_id)
        .first()
    )
    if not cred:
        return None, None
    try:
        return cred.tv_username, decrypt_secret(cred.tv_password_encrypted)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to decrypt TV credentials for user %s", user_id)
        return None, None


def run_job(job_id: str, as_of: str | None = None) -> str:
    """Execute the analysis job identified by ``job_id``. Returns final status.

    ``as_of`` is the "live now" timestamp (ISO string) the user ran the analysis
    at; when omitted the server stamps its own current UTC time.
    """
    db: Session = SessionLocal()
    try:
        job = db.get(AnalysisJob, job_id)
        if job is None:
            logger.error("Job %s not found", job_id)
            return "missing"

        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        job.error = None
        db.commit()

        # 1. Scrape TradingView
        tv_user, tv_pass = _resolve_tv_credentials(db, job.user_id)
        scrape = TradingViewScraper().scrape(job.symbol, job.timeframe, tv_user, tv_pass)
        raw = scrape.to_dict()

        snapshot = TradingViewSnapshot(
            job_id=job.id,
            symbol=job.symbol,
            timeframe=job.timeframe,
            price=raw.get("price"),
            technical_summary=raw.get("technical_summary"),
            raw_data=raw,
            screenshot_path=raw.get("screenshot_path"),
            extracted_text=raw.get("extracted_text"),
        )
        db.add(snapshot)
        db.commit()

        # 2. Run the agentic AI workflow
        state = run_analysis_workflow(job.symbol, job.timeframe, raw)
        report_content = state.get("report", {})

        # Stamp the "live now" moment the analysis was run as-of.
        report_content["analysis_as_of"] = as_of or datetime.now(timezone.utc).isoformat()

        # 3. Persist each agent's output
        for name, output in (state.get("agent_outputs") or {}).items():
            db.add(AgentOutput(job_id=job.id, agent_name=name, output=output))
        db.commit()

        # 4. Render PDF + persist report
        pdf_path = None
        try:
            pdf_path = generate_pdf(
                report_content, job.symbol, job.timeframe, raw.get("screenshot_path")
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF generation failed: %s", exc)

        report = Report(
            job_id=job.id,
            user_id=job.user_id,
            symbol=job.symbol,
            timeframe=job.timeframe,
            trend=report_content.get("trend"),
            confidence=report_content.get("confidence"),
            content=report_content,
            summary=report_content.get("executive_summary"),
            pdf_path=pdf_path,
        )
        db.add(report)

        job.status = JobStatus.completed
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        record_audit(db, action="analysis.completed", user_id=job.user_id, detail=job.symbol)
        logger.info("Job %s completed for %s", job_id, job.symbol)
        return "completed"

    except Exception as exc:  # noqa: BLE001
        logger.exception("Job %s failed", job_id)
        db.rollback()
        job = db.get(AnalysisJob, job_id)
        if job:
            job.status = JobStatus.failed
            job.error = str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        return "failed"
    finally:
        db.close()
