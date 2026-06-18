"""Generate a PDF report from structured analysis content using ReportLab."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import settings

REPORTS_DIR = os.path.join(os.path.dirname(settings.SCREENSHOT_DIR.rstrip("/")) or "/data", "reports")


def _styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle("H", parent=base["Heading2"], textColor=colors.HexColor("#1f6feb")))
    base.add(ParagraphStyle("Body2", parent=base["BodyText"], alignment=TA_LEFT, leading=14))
    return base


def generate_pdf(report: dict, symbol: str, timeframe: str, screenshot_path: str | None = None) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe = symbol.replace(":", "_").replace("/", "_")
    path = os.path.join(REPORTS_DIR, f"{safe}_{timeframe}_{ts}.pdf")

    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    s = _styles()
    story = []

    story.append(Paragraph("TradingView AI Analysis Report", s["Title"]))
    story.append(Paragraph(
        f"{symbol} &nbsp;•&nbsp; {timeframe} &nbsp;•&nbsp; "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        s["Normal"],
    ))
    story.append(Spacer(1, 8 * mm))

    setup = report.get("trade_setup", {}) or {}
    meta = [
        ["Trend", str(report.get("trend", "—")).upper()],
        ["Sentiment", str(report.get("sentiment", "—")).upper()],
        ["Confidence", f"{report.get('confidence', 0):.0f}%"],
        ["Entry", setup.get("entry", "—")],
        ["Stop Loss", setup.get("stop_loss", "—")],
        ["Target 1", setup.get("target_1", "—")],
        ["Target 2", setup.get("target_2", "—")],
        ["Risk / Reward", setup.get("risk_reward", "—")],
        ["Support", ", ".join(map(str, report.get("support", []))) or "—"],
        ["Resistance", ", ".join(map(str, report.get("resistance", []))) or "—"],
    ]
    table = Table(meta, colWidths=[45 * mm, 120 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f3f9")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0d7de")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 6 * mm))

    def section(title: str, body: str):
        if body:
            story.append(Paragraph(title, s["H"]))
            story.append(Paragraph(body.replace("\n", "<br/>"), s["Body2"]))
            story.append(Spacer(1, 4 * mm))

    section("Executive Summary", report.get("executive_summary", ""))
    section("Technical Analysis", report.get("technical_analysis", ""))
    section("Risk Analysis", report.get("risk_analysis", ""))
    section("AI Reasoning", report.get("ai_reasoning", ""))

    if screenshot_path and os.path.exists(screenshot_path):
        story.append(Paragraph("Chart Snapshot", s["H"]))
        try:
            story.append(Image(screenshot_path, width=165 * mm, height=92 * mm))
        except Exception:  # noqa: BLE001
            pass
        story.append(Spacer(1, 4 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"<i>{report.get('disclaimer', 'Educational use only. Not financial advice.')}</i>",
        s["Normal"],
    ))

    doc.build(story)
    return path
