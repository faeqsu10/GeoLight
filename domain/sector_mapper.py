"""이벤트 → 한국 섹터/종목 매핑."""

import logging
from typing import Optional

from config import SECTOR_MAP, SECTOR_STOCKS

logger = logging.getLogger("geolight.domain.mapper")


def map_event_to_sectors(event_type: str) -> Optional[dict]:
    """이벤트 유형 → 수혜/피해 섹터 + KRX 대표 종목 매핑.

    Returns:
        {
            "event_type": str,
            "beneficiary": [{"sector": str, "stocks": [{"name", "code"}]}],
            "damaged": [{"sector": str, "stocks": [{"name", "code"}]}],
        }
    """
    mapping = SECTOR_MAP.get(event_type)
    if not mapping:
        logger.warning("매핑 없는 이벤트: %s", event_type)
        return None

    result = {
        "event_type": event_type,
        "beneficiary": [],
        "damaged": [],
    }

    for sector_name in mapping.get("beneficiary", []):
        stocks = SECTOR_STOCKS.get(sector_name, [])
        result["beneficiary"].append({
            "sector": sector_name,
            "stocks": [s for s in stocks if s.get("code")],
        })

    for sector_name in mapping.get("damaged", []):
        stocks = SECTOR_STOCKS.get(sector_name, [])
        result["damaged"].append({
            "sector": sector_name,
            "stocks": [s for s in stocks if s.get("code")],
        })

    return result


def format_sector_summary(mapping: dict) -> str:
    """섹터 매핑 결과를 한글 요약 문자열로 포맷."""
    if not mapping:
        return "매핑 결과 없음"

    lines = []
    event_type = mapping["event_type"]
    lines.append(f"[{event_type}]")

    if mapping["beneficiary"]:
        sectors = ", ".join(b["sector"] for b in mapping["beneficiary"])
        lines.append(f"  수혜: {sectors}")
        for b in mapping["beneficiary"]:
            if b["stocks"]:
                stock_names = ", ".join(s["name"] for s in b["stocks"][:3])
                lines.append(f"    {b['sector']}: {stock_names}")

    if mapping["damaged"]:
        sectors = ", ".join(d["sector"] for d in mapping["damaged"])
        lines.append(f"  피해: {sectors}")
        for d in mapping["damaged"]:
            if d["stocks"]:
                stock_names = ", ".join(s["name"] for s in d["stocks"][:3])
                lines.append(f"    {d['sector']}: {stock_names}")

    return "\n".join(lines)


def translate_news_to_sectors(event_types: list[dict]) -> list[dict]:
    """분류된 이벤트 리스트 → 섹터 매핑 결과 리스트."""
    results = []
    for evt in event_types:
        mapping = map_event_to_sectors(evt["event_type"])
        if mapping:
            mapping["score"] = evt.get("score", 0.0)
            results.append(mapping)
    return results
