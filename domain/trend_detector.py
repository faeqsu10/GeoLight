"""관심 급증 종목 탐색 — 거래대금 급증 + 급락 후 반등 후보."""

import logging

from data.krx_data import get_top_volume_stocks, get_bounce_candidates

logger = logging.getLogger("geolight.domain.trend")


def detect_hot_stocks(top_n: int = 15) -> dict:
    """관심 급증 종목 탐색.

    Returns:
        {
            "top_volume": [...],     # 거래대금 상위
            "bounce_candidates": [...],  # 급락 후 반등 후보
        }
    """
    top_volume = get_top_volume_stocks(top_n=top_n)
    bounce = get_bounce_candidates(drop_threshold=-5.0, top_n=10)

    logger.info("핫 종목: 거래대금 %d건, 반등후보 %d건",
                len(top_volume), len(bounce))

    return {
        "top_volume": top_volume,
        "bounce_candidates": bounce,
    }


def format_hot_stocks(data: dict) -> str:
    """핫 종목 데이터를 텔레그램 메시지 형식으로 포맷."""
    lines = []

    # 거래대금 상위
    top_volume = data.get("top_volume", [])
    if top_volume:
        lines.append("거래대금 TOP")
        lines.append("-" * 25)
        for i, stock in enumerate(top_volume[:10], 1):
            value_억 = stock["trading_value"] / 100_000_000
            lines.append(f"{i}. {stock['name']} ({stock['code']}) — {value_억:,.0f}억")
    else:
        lines.append("거래대금 데이터 없음 (장 마감 또는 pykrx 미설치)")

    lines.append("")

    # 급락 후 반등 후보
    bounce = data.get("bounce_candidates", [])
    if bounce:
        lines.append("급락 후 반등 후보")
        lines.append("-" * 25)
        for i, stock in enumerate(bounce[:10], 1):
            lines.append(
                f"{i}. {stock['name']} ({stock['code']}) "
                f"{stock['change_pct']:+.1f}% / {stock['close']:,}원"
            )
    else:
        lines.append("반등 후보 없음")

    return "\n".join(lines)
