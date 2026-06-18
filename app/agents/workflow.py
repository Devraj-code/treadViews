"""LangGraph multi-agent analysis workflow.

Pipeline of collaborating agents:

    Market Reader -> Technical Analyst -> Risk Manager -> News Sentiment
                  -> Strategy -> Report Generator

Each node calls the configured LLM, records its structured output into the
shared state, and passes it downstream. The final node assembles a structured
report dict matching `schemas.trading.ReportContent`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.base import run_agent
from app.prompts import (
    DISCLAIMER,
    MARKET_READER_PROMPT,
    NEWS_SENTIMENT_PROMPT,
    REPORT_GENERATOR_PROMPT,
    RISK_MANAGER_PROMPT,
    STRATEGY_PROMPT,
    TECHNICAL_ANALYST_PROMPT,
)
from app.services.news import fetch_news

logger = logging.getLogger(__name__)


class AnalysisState(TypedDict, total=False):
    symbol: str
    timeframe: str
    raw_data: dict
    observation: dict
    technical: dict
    risk: dict
    sentiment: dict
    strategy: dict
    report: dict
    agent_outputs: dict  # agent_name -> output, for persistence


def _record(state: AnalysisState, name: str, output: dict) -> None:
    state.setdefault("agent_outputs", {})[name] = output


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def market_reader(state: AnalysisState) -> AnalysisState:
    out = run_agent(
        "You normalise raw market data into clean observations.",
        MARKET_READER_PROMPT.format(
            symbol=state["symbol"],
            timeframe=state["timeframe"],
            raw_data=json.dumps(state.get("raw_data", {}))[:6000],
        ),
    )
    # Fall back to raw data if the LLM produced nothing usable.
    if not out or "_error" in out:
        raw = state.get("raw_data", {})
        out = {
            "symbol": state["symbol"],
            "timeframe": state["timeframe"],
            "price": raw.get("price"),
            "technical_summary": raw.get("technical_summary"),
            "indicators": raw.get("indicators", {}),
            "support_hints": raw.get("support_levels", []),
            "resistance_hints": raw.get("resistance_levels", []),
            "notable_text": (raw.get("extracted_text") or "")[:400],
        }
    state["observation"] = out
    _record(state, "market_reader", out)
    return state


def technical_analyst(state: AnalysisState) -> AnalysisState:
    out = run_agent(
        "You are an expert technical analyst.",
        TECHNICAL_ANALYST_PROMPT.format(observation=json.dumps(state.get("observation", {}))),
    )
    state["technical"] = out
    _record(state, "technical_analyst", out)
    return state


def risk_manager(state: AnalysisState) -> AnalysisState:
    price = state.get("observation", {}).get("price")
    out = run_agent(
        "You are a disciplined risk manager.",
        RISK_MANAGER_PROMPT.format(price=price, technical=json.dumps(state.get("technical", {}))),
    )
    state["risk"] = out
    _record(state, "risk_manager", out)
    return state


def news_sentiment(state: AnalysisState) -> AnalysisState:
    news = fetch_news(state["symbol"])
    headlines = [n["title"] for n in news]
    out = run_agent(
        "You assess market sentiment from news.",
        NEWS_SENTIMENT_PROMPT.format(
            symbol=state["symbol"],
            headlines="\n".join(f"- {h}" for h in headlines) or "(none available)",
            trend=state.get("technical", {}).get("trend", "neutral"),
        ),
    )
    out.setdefault("headlines_used", headlines)
    # Keep the full source records (title + url + source) for the report.
    out["news"] = news
    state["sentiment"] = out
    _record(state, "news_sentiment", out)
    return state


def strategy_agent(state: AnalysisState) -> AnalysisState:
    out = run_agent(
        "You synthesise multiple analyses into a single strategy.",
        STRATEGY_PROMPT.format(
            symbol=state["symbol"],
            timeframe=state["timeframe"],
            technical=json.dumps(state.get("technical", {})),
            risk=json.dumps(state.get("risk", {})),
            sentiment=json.dumps(state.get("sentiment", {})),
        ),
    )
    state["strategy"] = out
    _record(state, "strategy", out)
    return state


def report_generator(state: AnalysisState) -> AnalysisState:
    combined = {
        "observation": state.get("observation", {}),
        "technical": state.get("technical", {}),
        "risk": state.get("risk", {}),
        "sentiment": state.get("sentiment", {}),
        "strategy": state.get("strategy", {}),
    }
    out = run_agent(
        "You write professional, educational trading reports.",
        REPORT_GENERATOR_PROMPT.format(
            symbol=state["symbol"], timeframe=state["timeframe"], combined=json.dumps(combined)
        ),
    )
    technical = state.get("technical", {})
    risk = state.get("risk", {})
    strategy = state.get("strategy", {})
    sentiment = state.get("sentiment", {})
    raw = state.get("raw_data", {})
    confidence = out.get("confidence") or strategy.get("confidence") or 50

    # Snapshot of the underlying scrape so the UI can show "today + all the data"
    # behind the chart image, not just the picture.
    snapshot = {
        "price": raw.get("price"),
        "technical_summary": raw.get("technical_summary"),
        "indicators": raw.get("indicators", {}),
        "scraped_at": raw.get("scraped_at"),
        "support_levels": raw.get("support_levels", []),
        "resistance_levels": raw.get("resistance_levels", []),
    }

    report = {
        "executive_summary": out.get("executive_summary", ""),
        "technical_analysis": out.get("technical_analysis", technical.get("analysis", "")),
        "risk_analysis": out.get("risk_analysis", risk.get("risk_analysis", "")),
        "trade_setup": {
            "entry": risk.get("entry"),
            "stop_loss": risk.get("stop_loss"),
            "target_1": risk.get("target_1"),
            "target_2": risk.get("target_2"),
            "risk_reward": risk.get("risk_reward"),
        },
        "support": technical.get("support", []),
        "resistance": technical.get("resistance", []),
        "trend": strategy.get("final_bias", technical.get("trend", "neutral")),
        "sentiment": sentiment.get("sentiment", "neutral"),
        "candlestick_patterns": technical.get("candlestick_patterns", []),
        "confidence": float(confidence),
        "ai_reasoning": out.get("ai_reasoning", strategy.get("strategy_summary", "")),
        # Why the call is bullish / bearish, plus the evidence behind it.
        "why_bias": out.get("why_bias", strategy.get("strategy_summary", "")),
        "key_drivers": strategy.get("key_drivers", []),
        "sentiment_score": sentiment.get("score"),
        "sentiment_rationale": sentiment.get("rationale", ""),
        "news": sentiment.get("news", []),
        "snapshot": snapshot,
        "disclaimer": DISCLAIMER,
    }
    state["report"] = report
    _record(state, "report_generator", report)
    return state


# --------------------------------------------------------------------------- #
# Graph assembly
# --------------------------------------------------------------------------- #
def build_graph() -> Callable:
    graph = StateGraph(AnalysisState)
    graph.add_node("market_reader", market_reader)
    graph.add_node("technical_analyst", technical_analyst)
    graph.add_node("risk_manager", risk_manager)
    graph.add_node("news_sentiment", news_sentiment)
    graph.add_node("strategy", strategy_agent)
    graph.add_node("report_generator", report_generator)

    graph.add_edge(START, "market_reader")
    graph.add_edge("market_reader", "technical_analyst")
    graph.add_edge("technical_analyst", "risk_manager")
    graph.add_edge("risk_manager", "news_sentiment")
    graph.add_edge("news_sentiment", "strategy")
    graph.add_edge("strategy", "report_generator")
    graph.add_edge("report_generator", END)
    return graph.compile()


_COMPILED = None


def run_analysis_workflow(symbol: str, timeframe: str, raw_data: dict) -> AnalysisState:
    """Run the full agentic workflow and return the final state."""
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_graph()
    initial: AnalysisState = {
        "symbol": symbol,
        "timeframe": timeframe,
        "raw_data": raw_data,
        "agent_outputs": {},
    }
    return _COMPILED.invoke(initial)
