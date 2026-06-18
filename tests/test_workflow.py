"""Test the agentic workflow with a stubbed LLM (no network)."""
import app.agents.base as base
import app.agents.workflow as wf


def _fake_run_agent(system, prompt):
    """Return plausible structured output based on which agent is calling."""
    if "Market Reader" in prompt or "normalise" in prompt:
        return {"price": 100.0, "indicators": {"RSI": 60}, "support_hints": [95], "resistance_hints": [110]}
    if "Technical Analyst" in prompt:
        return {"trend": "bullish", "support": [95, 90], "resistance": [110, 115],
                "candlestick_patterns": ["bullish engulfing"], "momentum": "rising", "analysis": "Uptrend."}
    if "Risk Management" in prompt:
        return {"entry": 101, "stop_loss": 96, "target_1": 110, "target_2": 115,
                "risk_reward": "1:1.8", "risk_analysis": "Controlled risk."}
    if "News Sentiment" in prompt:
        return {"sentiment": "bullish", "score": 0.4, "rationale": "Positive flow."}
    if "Strategy" in prompt:
        return {"final_bias": "bullish", "confidence": 72, "key_drivers": ["momentum"],
                "strategy_summary": "Buy the dip."}
    if "Report Generator" in prompt:
        return {"executive_summary": "Bullish setup.", "technical_analysis": "Above EMAs.",
                "risk_analysis": "Tight stop.", "ai_reasoning": "Momentum + sentiment align.", "confidence": 75}
    return {}


def test_workflow_produces_full_report(monkeypatch):
    monkeypatch.setattr(base, "run_agent", _fake_run_agent)
    monkeypatch.setattr(wf, "run_agent", _fake_run_agent)
    monkeypatch.setattr(wf, "fetch_headlines", lambda symbol: ["Big rally expected"])

    # Rebuild the compiled graph so it binds the patched node functions.
    wf._COMPILED = None
    state = wf.run_analysis_workflow("NSE:NIFTY", "1D", {"price": 100.0})

    report = state["report"]
    assert report["trend"] == "bullish"
    assert report["confidence"] == 75
    assert report["trade_setup"]["entry"] == 101
    assert report["support"] == [95, 90]
    assert "disclaimer" in report
    assert set(["market_reader", "technical_analyst", "risk_manager",
                "news_sentiment", "strategy", "report_generator"]).issubset(state["agent_outputs"].keys())
