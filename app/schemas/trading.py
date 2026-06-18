"""Trading / analysis / watchlist / schedule / report schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# --------------------------- Watchlist --------------------------- #
class WatchlistCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=50)
    exchange: str = ""
    timeframe: str = "1D"
    note: str = ""


class WatchlistOut(WatchlistCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


# --------------------------- Analysis --------------------------- #
class AnalysisRunRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=50)
    timeframe: str = "1D"
    indicators: List[str] = Field(default_factory=lambda: ["RSI", "MACD", "EMA"])
    # Client-supplied "live now" timestamp the analysis is run as-of. When the
    # user enables the "Live now" option the frontend sends the current local
    # date/time here; left null the server stamps its own current time.
    as_of: Optional[datetime] = None


class AnalysisJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    symbol: str
    timeframe: str
    indicators: List[str]
    status: str
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


# --------------------------- Reports --------------------------- #
class TradeSetup(BaseModel):
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    target_1: Optional[float] = None
    target_2: Optional[float] = None
    risk_reward: Optional[str] = None


class NewsItem(BaseModel):
    title: str = ""
    url: str = ""
    source: str = ""
    published_at: str = ""


class SnapshotInfo(BaseModel):
    price: Optional[float] = None
    technical_summary: Optional[str] = None
    indicators: dict[str, Any] = Field(default_factory=dict)
    scraped_at: Optional[str] = None
    support_levels: List[float] = Field(default_factory=list)
    resistance_levels: List[float] = Field(default_factory=list)


class ReportContent(BaseModel):
    executive_summary: str = ""
    technical_analysis: str = ""
    risk_analysis: str = ""
    trade_setup: TradeSetup = Field(default_factory=TradeSetup)
    support: List[float] = Field(default_factory=list)
    resistance: List[float] = Field(default_factory=list)
    trend: str = "neutral"
    sentiment: str = "neutral"
    candlestick_patterns: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    ai_reasoning: str = ""
    # Why the call is bullish/bearish + the evidence behind it.
    why_bias: str = ""
    key_drivers: List[str] = Field(default_factory=list)
    sentiment_score: Optional[float] = None
    sentiment_rationale: str = ""
    news: List[NewsItem] = Field(default_factory=list)
    snapshot: SnapshotInfo = Field(default_factory=SnapshotInfo)
    analysis_as_of: Optional[str] = None
    disclaimer: str = "This analysis is educational only and not financial advice."


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str
    symbol: str
    timeframe: str
    trend: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None
    content: dict[str, Any]
    pdf_path: Optional[str] = None
    created_at: datetime


# --------------------------- Schedule --------------------------- #
class ScheduleCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=50)
    timeframe: str = "1D"
    indicators: List[str] = Field(default_factory=lambda: ["RSI", "MACD"])
    interval: str = Field(description="every_5_min | every_15_min | hourly | daily")


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    symbol: str
    timeframe: str
    indicators: List[str]
    interval: str
    is_active: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime


# --------------------------- Dashboard --------------------------- #
class DashboardSummary(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_reports: int
    active_schedules: int
    watchlist_count: int
    recent_reports: List[ReportOut]
