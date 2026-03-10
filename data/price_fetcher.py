"""가격 데이터 수집 — 유가, 환율, VIX, KOSPI."""

import logging
import time
from typing import Optional

import yfinance as yf

logger = logging.getLogger("geolight.data.price")

# Yahoo Finance 티커 매핑
_TICKERS = {
    "oil_wti": "CL=F",       # WTI 원유 선물
    "oil_brent": "BZ=F",     # Brent 원유 선물
    "usd_krw": "KRW=X",      # USD/KRW 환율
    "vix": "^VIX",            # VIX 공포지수
    "kospi": "^KS11",         # KOSPI 지수
}

# 캐시 (5분 TTL)
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 5 * 60


def _get_cached(key: str) -> Optional[dict]:
    if key in _cache:
        cached_time, cached_data = _cache[key]
        if time.time() - cached_time < _CACHE_TTL:
            return cached_data
    return None


def fetch_price(indicator: str) -> Optional[dict]:
    """단일 지표의 현재가 + 전일 대비 변동률 조회."""
    cached = _get_cached(indicator)
    if cached:
        return cached

    ticker_symbol = _TICKERS.get(indicator)
    if not ticker_symbol:
        logger.warning("알 수 없는 지표: %s", indicator)
        return None

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="5d")
        if hist.empty or len(hist) < 2:
            logger.warning("가격 데이터 부족: %s", indicator)
            return None

        current = float(hist["Close"].iloc[-1])
        previous = float(hist["Close"].iloc[-2])
        change_pct = ((current - previous) / previous) * 100 if previous else 0.0

        result = {
            "indicator": indicator,
            "value": round(current, 2),
            "prev_value": round(previous, 2),
            "change_pct": round(change_pct, 2),
        }

        _cache[indicator] = (time.time(), result)
        logger.info("[%s] %.2f (%.2f%%)", indicator, current, change_pct)
        return result

    except Exception as e:
        logger.warning("가격 조회 실패 [%s]: %s", indicator, e)
        return None


def fetch_all_prices() -> dict[str, dict]:
    """모든 지표의 가격을 한 번에 조회."""
    results = {}
    for indicator in _TICKERS:
        price = fetch_price(indicator)
        if price:
            results[indicator] = price
        time.sleep(0.3)
    return results
