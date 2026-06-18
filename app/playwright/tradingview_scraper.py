"""Playwright-based TradingView scraper.

Launches headless Chromium, optionally logs in, opens a symbol chart, and
extracts the current price, technical summary, indicators, support/resistance
hints, and a full-page screenshot. Network and selector failures are retried.

TradingView's DOM changes frequently; selectors are centralised here and the
scraper degrades gracefully (returning whatever it could read) rather than
failing the whole job.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings

logger = logging.getLogger(__name__)

CHART_URL = "https://www.tradingview.com/chart/?symbol={symbol}"
SYMBOL_URL = "https://www.tradingview.com/symbols/{symbol}/"
TECHNICALS_URL = "https://www.tradingview.com/symbols/{symbol}/technicals/"


@dataclass
class ScrapeResult:
    symbol: str
    timeframe: str
    price: Optional[float] = None
    technical_summary: Optional[str] = None  # STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
    indicators: dict = field(default_factory=dict)
    support_levels: list = field(default_factory=list)
    resistance_levels: list = field(default_factory=list)
    extracted_text: str = ""
    screenshot_path: Optional[str] = None
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _to_float(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


class TradingViewScraper:
    def __init__(self, headless: Optional[bool] = None, timeout_ms: Optional[int] = None):
        self.headless = settings.PLAYWRIGHT_HEADLESS if headless is None else headless
        self.timeout_ms = timeout_ms or settings.PLAYWRIGHT_TIMEOUT_MS
        os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)

    # --------------------------------------------------------------------- #
    def scrape(
        self,
        symbol: str,
        timeframe: str = "1D",
        tv_username: Optional[str] = None,
        tv_password: Optional[str] = None,
    ) -> ScrapeResult:
        """Public entry point. Always returns a ScrapeResult (never raises)."""
        result = ScrapeResult(symbol=symbol, timeframe=timeframe)
        try:
            self._run(symbol, timeframe, tv_username, tv_password, result)
        except Exception as exc:  # noqa: BLE001 — scraper must degrade gracefully
            logger.exception("Scrape failed for %s", symbol)
            result.error = str(exc)
        return result

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(PWTimeout),
    )
    def _goto(self, page: Page, url: str) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)

    def _run(self, symbol, timeframe, tv_username, tv_password, result: ScrapeResult) -> None:
        launch_args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        with sync_playwright() as p:
            try:
                # Prefer a configured system channel (e.g. "chrome") when set,
                # otherwise use the bundled Chromium.
                if settings.PLAYWRIGHT_CHANNEL:
                    browser = p.chromium.launch(
                        headless=self.headless,
                        channel=settings.PLAYWRIGHT_CHANNEL,
                        args=launch_args,
                    )
                else:
                    browser = p.chromium.launch(headless=self.headless, args=launch_args)
            except Exception:  # noqa: BLE001 — fall back to system Chrome if Chromium missing
                logger.warning("Chromium launch failed; falling back to system 'chrome' channel")
                browser = p.chromium.launch(headless=self.headless, channel="chrome", args=launch_args)
            context = browser.new_context(
                viewport={"width": 1600, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                if tv_username and tv_password:
                    self._login(page, tv_username, tv_password)

                # 1. Technicals page — most reliable structured data.
                self._scrape_technicals(page, symbol, result)
                # 2. Chart screenshot.
                self._capture_chart(page, symbol, timeframe, result)
            finally:
                context.close()
                browser.close()

    # --------------------------------------------------------------------- #
    def _login(self, page: Page, username: str, password: str) -> None:
        try:
            self._goto(page, "https://www.tradingview.com/accounts/signin/")
            page.click("button:has-text('Email')", timeout=8000)
            page.fill("input[name='id_username']", username, timeout=8000)
            page.fill("input[name='id_password']", password, timeout=8000)
            page.click("button[type='submit']", timeout=8000)
            page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
            logger.info("TradingView login submitted for %s", username)
        except PWTimeout:
            logger.warning("TradingView login flow timed out; continuing anonymously")

    def _scrape_technicals(self, page: Page, symbol: str, result: ScrapeResult) -> None:
        self._goto(page, TECHNICALS_URL.format(symbol=symbol))
        try:
            page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        except PWTimeout:
            pass

        body_text = ""
        try:
            body_text = page.inner_text("body", timeout=8000)
        except PWTimeout:
            pass
        result.extracted_text = body_text[:8000]

        # Technical summary gauge (Strong Buy / Buy / Neutral / Sell / Strong Sell)
        for label in ("Strong buy", "Strong sell", "Buy", "Sell", "Neutral"):
            if re.search(rf"\b{label}\b", body_text, re.IGNORECASE):
                result.technical_summary = label.upper().replace(" ", "_")
                break

        # Current price — look for the large price element.
        for sel in [
            "[class*='last-'] [class*='price']",
            "span[class*='symbol-price']",
            "div[class*='lastContainer'] span",
        ]:
            try:
                txt = page.inner_text(sel, timeout=3000)
                price = _to_float(txt)
                if price:
                    result.price = price
                    break
            except PWTimeout:
                continue

        # Pivot-based support/resistance from the Pivots table, if present.
        result.support_levels, result.resistance_levels = self._parse_pivots(body_text, result.price)

        # Capture a handful of indicator readings heuristically from the text.
        result.indicators = self._parse_indicators(body_text)

    def _capture_chart(self, page: Page, symbol: str, timeframe: str, result: ScrapeResult) -> None:
        self._goto(page, CHART_URL.format(symbol=symbol))
        try:
            page.wait_for_selector("canvas", timeout=self.timeout_ms)
            page.wait_for_timeout(4000)  # let the chart finish rendering
        except PWTimeout:
            logger.warning("Chart canvas not detected for %s", symbol)

        safe = re.sub(r"[^A-Za-z0-9_]", "_", symbol)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = os.path.join(settings.SCREENSHOT_DIR, f"{safe}_{timeframe}_{ts}.png")
        try:
            page.screenshot(path=path, full_page=False)
            result.screenshot_path = path
        except Exception as exc:  # noqa: BLE001
            logger.warning("Screenshot failed: %s", exc)

    # --------------------------------------------------------------------- #
    @staticmethod
    def _parse_pivots(text: str, price: Optional[float]) -> tuple[list, list]:
        nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*\.\d+", text)]
        if not nums or price is None:
            return [], []
        below = sorted({n for n in nums if n < price}, reverse=True)[:3]
        above = sorted({n for n in nums if n > price})[:3]
        return below, above

    @staticmethod
    def _parse_indicators(text: str) -> dict:
        indicators: dict = {}
        m = re.search(r"RSI\s*\(?14?\)?\D*([0-9]{1,3}\.?[0-9]*)", text, re.IGNORECASE)
        if m:
            indicators["RSI"] = _to_float(m.group(1))
        for name in ("MACD", "Stochastic", "ADX", "CCI"):
            if name.lower() in text.lower():
                indicators.setdefault(name, "present")
        return indicators


def scrape_symbol(
    symbol: str,
    timeframe: str = "1D",
    tv_username: Optional[str] = None,
    tv_password: Optional[str] = None,
) -> dict:
    """Convenience wrapper returning a plain dict (used by agents/tasks)."""
    return TradingViewScraper().scrape(symbol, timeframe, tv_username, tv_password).to_dict()
