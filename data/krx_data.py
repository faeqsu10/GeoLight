"""KRX 종목/섹터 데이터 — pykrx 개별 종목 조회 기반."""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("geolight.data.krx")

try:
    from pykrx import stock as krx_stock
    _PYKRX_AVAILABLE = True
except ImportError:
    logger.warning("pykrx 미설치. KRX 실시간 데이터 비활성화.")
    _PYKRX_AVAILABLE = False


def _recent_business_days(n: int = 2) -> tuple[str, str]:
    """최근 n 영업일의 (시작일, 종료일) YYYYMMDD 반환."""
    end = datetime.now()
    while end.weekday() >= 5:
        end -= timedelta(days=1)
    start = end - timedelta(days=n + 4)  # 주말 고려 여유분
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


# ── 주요 종목 코드 (config의 SECTOR_STOCKS에서 사용하는 대표 종목) ──
_MAJOR_CODES = [
    ("005930", "삼성전자"), ("000660", "SK하이닉스"), ("005380", "현대차"),
    ("000270", "기아"), ("005490", "POSCO홀딩스"), ("096770", "SK이노베이션"),
    ("105560", "KB금융"), ("055550", "신한지주"), ("035720", "카카오"),
    ("035420", "네이버"), ("003490", "대한항공"), ("012450", "한화에어로스페이스"),
    ("207940", "삼성바이오로직스"), ("068270", "셀트리온"), ("051910", "LG화학"),
    ("010950", "S-Oil"), ("009540", "HD한국조선해양"), ("352820", "하이브"),
    ("015760", "한국전력"), ("066570", "LG전자"), ("009150", "삼성전기"),
    ("004020", "현대제철"), ("011200", "HMM"), ("047810", "한국항공우주"),
    ("086790", "하나금융지주"), ("028670", "팬오션"), ("036460", "한국가스공사"),
    ("090430", "아모레퍼시픽"), ("039130", "하나투어"), ("004170", "신세계"),
]


def _fetch_stock_data(code: str) -> Optional[dict]:
    """개별 종목의 최근 OHLCV 데이터 조회."""
    if not _PYKRX_AVAILABLE:
        return None

    start, end = _recent_business_days(5)
    try:
        df = krx_stock.get_market_ohlcv(start, end, code)
        if df.empty or len(df) < 2:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2]
        close = int(last["종가"])
        prev_close = int(prev["종가"])
        change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0
        volume = int(last["거래량"])

        return {
            "code": code,
            "close": close,
            "prev_close": prev_close,
            "change_pct": round(change_pct, 2),
            "volume": volume,
        }
    except Exception as e:
        logger.debug("종목 %s 조회 실패: %s", code, e)
        return None


def get_top_volume_stocks(top_n: int = 20) -> list[dict]:
    """주요 종목 중 거래량 상위 종목 조회."""
    if not _PYKRX_AVAILABLE:
        return []

    results = []
    for code, name in _MAJOR_CODES:
        data = _fetch_stock_data(code)
        if data:
            data["name"] = name
            # 거래대금 추정 (거래량 × 종가)
            data["trading_value"] = data["volume"] * data["close"]
            results.append(data)

    results.sort(key=lambda x: x["trading_value"], reverse=True)
    logger.info("거래대금 상위 %d종목 조회 완료", min(top_n, len(results)))
    return results[:top_n]


def get_bounce_candidates(drop_threshold: float = -5.0, top_n: int = 10) -> list[dict]:
    """급락 후 반등 후보 — 전일 대비 큰 폭 하락 + 거래량 많은 종목."""
    if not _PYKRX_AVAILABLE:
        return []

    results = []
    for code, name in _MAJOR_CODES:
        data = _fetch_stock_data(code)
        if data and data["change_pct"] <= drop_threshold:
            data["name"] = name
            results.append(data)

    results.sort(key=lambda x: x["volume"], reverse=True)
    logger.info("반등 후보 %d종목 탐색", len(results))
    return results[:top_n]
