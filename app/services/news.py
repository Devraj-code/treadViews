"""Fetch recent news for a symbol (best-effort, with sources).

Order of preference:
  1. NewsAPI (https://newsapi.org) when ``NEWS_API_KEY`` is configured.
  2. Google News RSS — keyless, works out of the box, so the News Sentiment
     Agent and the report always have real headlines + clickable sources.

Every fetch degrades to an empty list on failure so a job never breaks because
news was unavailable.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# How a TradingView symbol maps to a human news query, e.g. "NSE:NIFTY" -> "NIFTY".
_SYMBOL_HINTS = {
    "NIFTY": "Nifty 50 index",
    "BANKNIFTY": "Bank Nifty index",
    "BTCUSDT": "Bitcoin",
    "ETHUSDT": "Ethereum",
}


def _query_for(symbol: str) -> str:
    base = symbol.split(":")[-1].upper()
    return _SYMBOL_HINTS.get(base, base)


def fetch_news(symbol: str, limit: int = 8) -> list[dict]:
    """Return a list of ``{title, url, source, published_at}`` dicts (newest first)."""
    query = _query_for(symbol)
    if settings.NEWS_API_KEY:
        items = _from_newsapi(query, limit)
        if items:
            return items
    return _from_google_rss(query, limit)


def fetch_headlines(symbol: str, limit: int = 8) -> list[str]:
    """Backward-compatible helper: just the headline strings."""
    return [n["title"] for n in fetch_news(symbol, limit) if n.get("title")][:limit]


def _from_newsapi(query: str, limit: int) -> list[dict]:
    try:
        resp = httpx.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": limit,
                "apiKey": settings.NEWS_API_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return [
            {
                "title": a.get("title", "").strip(),
                "url": a.get("url", ""),
                "source": (a.get("source") or {}).get("name", "NewsAPI"),
                "published_at": a.get("publishedAt", ""),
            }
            for a in resp.json().get("articles", [])
            if a.get("title")
        ][:limit]
    except Exception as exc:  # noqa: BLE001
        logger.warning("NewsAPI fetch failed for %s: %s", query, exc)
        return []


def _from_google_rss(query: str, limit: int) -> list[dict]:
    """Keyless fallback using the public Google News RSS feed."""
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query + " when:7d")
        + "&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        items: list[dict] = []
        for item in root.iterfind(".//item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            # Google appends " - Source" to titles; split it back out.
            source_el = item.find("source")
            source = (source_el.text or "").strip() if source_el is not None else ""
            if not source and " - " in title:
                title, source = title.rsplit(" - ", 1)
            items.append({
                "title": title,
                "url": (item.findtext("link") or "").strip(),
                "source": source or "Google News",
                "published_at": (item.findtext("pubDate") or "").strip(),
            })
            if len(items) >= limit:
                break
        return items
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google News fetch failed for %s: %s", query, exc)
        return []
