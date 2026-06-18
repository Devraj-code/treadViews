"""Prompt templates for each agent in the analysis workflow."""

DISCLAIMER = "This analysis is educational only and not financial advice."

MARKET_READER_PROMPT = """You are the Market Reader Agent.
You are given RAW data scraped from TradingView for {symbol} on the {timeframe} timeframe.
Clean and normalise it into a compact factual observation. Do NOT analyse or give opinions.

Raw scraped data (JSON):
{raw_data}

Return STRICT JSON with keys:
  symbol, timeframe, price (number or null), technical_summary (string or null),
  indicators (object), support_hints (array of numbers), resistance_hints (array of numbers),
  notable_text (short string summarising any visible textual info).
"""

TECHNICAL_ANALYST_PROMPT = """You are the Technical Analyst Agent, an expert chart technician.
Given the cleaned market observation below, determine the technical picture.

Observation (JSON):
{observation}

Analyse: trend direction, support & resistance, breakouts, reversals, candlestick
patterns, and momentum. Be specific and quantitative where the data allows.

Return STRICT JSON with keys:
  trend ("bullish"|"bearish"|"neutral"),
  support (array of numbers, strongest first),
  resistance (array of numbers, strongest first),
  candlestick_patterns (array of strings),
  momentum ("rising"|"falling"|"flat"),
  breakout (string), reversal_risk ("low"|"medium"|"high"),
  analysis (2-4 sentence narrative).
"""

RISK_MANAGER_PROMPT = """You are the Risk Management Agent.
Using the technical analysis and current price, propose a concrete trade setup.

Current price: {price}
Technical analysis (JSON):
{technical}

Return STRICT JSON with keys:
  entry (number), stop_loss (number), target_1 (number), target_2 (number),
  risk_reward (string like "1:2.7"), position_sizing_note (string),
  risk_analysis (2-3 sentence narrative).
Ensure stop_loss and targets are consistent with the trend direction.
"""

NEWS_SENTIMENT_PROMPT = """You are the News Sentiment Agent.
Assess market sentiment for {symbol} based on the headlines provided. If no
headlines are available, infer a neutral-to-cautious sentiment from the technicals.

Headlines:
{headlines}

Technical trend: {trend}

Return STRICT JSON with keys:
  sentiment ("bullish"|"bearish"|"neutral"),
  score (number between -1 and 1),
  rationale (1-2 sentences).
"""

STRATEGY_PROMPT = """You are the Strategy Agent. Combine all agent outputs into a
single coherent trading view for {symbol} ({timeframe}).

Technical analysis: {technical}
Risk setup: {risk}
Sentiment: {sentiment}

Resolve conflicts (e.g. bullish technicals vs bearish sentiment) and state a final
directional bias with a confidence percentage (0-100).

Return STRICT JSON with keys:
  final_bias ("bullish"|"bearish"|"neutral"),
  confidence (number 0-100),
  key_drivers (array of short strings),
  strategy_summary (2-4 sentences).
"""

REPORT_GENERATOR_PROMPT = """You are the Report Generator Agent. Produce a polished,
human-readable trading report for {symbol} ({timeframe}) from the combined analysis.

The combined analysis includes technical, risk, sentiment (with real news headlines
and their sources), and strategy outputs.

Combined analysis (JSON):
{combined}

Write clear, professional prose. Return STRICT JSON with keys:
  executive_summary (string),
  technical_analysis (string),
  risk_analysis (string),
  ai_reasoning (string, explain WHY in plain language),
  why_bias (string, 3-5 sentences: explain in FULL DETAIL WHY the outlook is
    bullish, bearish, or neutral. Explicitly connect the call to the evidence —
    cite specific technical signals AND specific news headlines/sources from the
    sentiment data. If no news was available, say so and rely on technicals.),
  confidence (number 0-100).
Always end nothing with advice — this is educational only.
"""
