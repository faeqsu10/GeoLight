"""가격 데이터 수집 — 유가, 환율, VIX, KOSPI."""

import logging
import time
from typing import Optional

import yfinance as yf
from config import INDICATORS

logger = logging.getLogger("geolight.data.price")

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

    indicator_config = INDICATORS.get(indicator)
    ticker_symbol = indicator_config.get("ticker") if indicator_config else None
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


def build_indicators(prices: dict) -> dict:
    """가격 데이터를 시나리오/액션 엔진용 indicators dict로 변환."""
    indicators = {}
    for ind, p in prices.items():
        indicators[f"{ind}_change_pct"] = p["change_pct"]
        indicators[ind] = p["value"]
    return indicators


def fetch_all_prices() -> dict[str, dict]:
    """모든 지표의 가격을 병렬로 조회."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}
    indicators = list(INDICATORS.keys())

    # 캐시된 것은 바로 반환, 나머지만 병렬 요청
    to_fetch = []
    for ind in indicators:
        cached = _get_cached(ind)
        if cached:
            results[ind] = cached
        else:
            to_fetch.append(ind)

    if not to_fetch:
        return results

    with ThreadPoolExecutor(max_workers=len(to_fetch)) as executor:
        futures = {executor.submit(fetch_price, ind): ind for ind in to_fetch}
        for future in as_completed(futures):
            ind = futures[future]
            try:
                price = future.result()
                if price:
                    results[ind] = price
            except Exception as e:
                logger.warning("병렬 가격 조회 실패 [%s]: %s", ind, e)

    return results
