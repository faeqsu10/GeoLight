"""시나리오 기반 투자 지도 — 현재 지표로 시나리오 매칭."""

import logging
from typing import Optional

from config import SCENARIOS, SECTOR_STOCKS

logger = logging.getLogger("geolight.domain.scenario")


def evaluate_scenario(scenario_key: str, indicators: dict) -> dict:
    """단일 시나리오의 매칭 점수를 계산.

    Args:
        scenario_key: SCENARIOS 키
        indicators: {"oil_change_pct": float, "vix": float, ...}

    Returns:
        {"key": str, "name": str, "score": float, "matched": list, ...}
    """
    scenario = SCENARIOS.get(scenario_key)
    if not scenario:
        return {"key": scenario_key, "score": 0.0, "matched": []}

    matched_conditions = []
    total_conditions = 0

    for ind_key, (low, high) in scenario["indicators"].items():
        total_conditions += 1
        value = indicators.get(ind_key)
        if value is None:
            continue

        if low is not None and high is not None:
            if low <= value <= high:
                matched_conditions.append(f"{ind_key}={value}")
        elif low is not None:
            if value >= low:
                matched_conditions.append(f"{ind_key}={value} (>={low})")
        elif high is not None:
            if value <= high:
                matched_conditions.append(f"{ind_key}={value} (<={high})")

    score = len(matched_conditions) / total_conditions if total_conditions > 0 else 0.0

    return {
        "key": scenario_key,
        "name": scenario["name"],
        "description": scenario["description"],
        "score": round(score, 2),
        "matched": matched_conditions,
        "beneficiary_sectors": scenario["beneficiary_sectors"],
        "damaged_sectors": scenario["damaged_sectors"],
    }


def find_best_scenario(indicators: dict) -> Optional[dict]:
    """현재 지표 기반으로 가장 적합한 시나리오 반환."""
    results = []
    for key in SCENARIOS:
        result = evaluate_scenario(key, indicators)
        if result["score"] > 0:
            results.append(result)

    if not results:
        return None

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[0]


def get_all_scenarios_status(indicators: dict) -> list[dict]:
    """모든 시나리오의 매칭 상태 반환 (점수 내림차순)."""
    results = []
    for key in SCENARIOS:
        result = evaluate_scenario(key, indicators)
        results.append(result)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def format_scenario_card(scenario: dict) -> str:
    """시나리오를 텔레그램용 카드 형식으로 포맷."""
    if not scenario:
        return "현재 매칭되는 시나리오가 없습니다."

    lines = [
        f"{'='*30}",
        f"시나리오: {scenario['name']}",
        f"{'='*30}",
        f"설명: {scenario['description']}",
        f"매칭 점수: {scenario['score'] * 100:.0f}%",
    ]

    if scenario.get("matched"):
        lines.append(f"충족 조건: {', '.join(scenario['matched'])}")

    if scenario.get("beneficiary_sectors"):
        sectors = ", ".join(scenario["beneficiary_sectors"])
        lines.append(f"\n수혜 섹터: {sectors}")
        for sector in scenario["beneficiary_sectors"][:5]:
            stocks = SECTOR_STOCKS.get(sector, [])
            if stocks:
                names = ", ".join(s["name"] for s in stocks[:3])
                lines.append(f"  {sector}: {names}")

    if scenario.get("damaged_sectors"):
        sectors = ", ".join(scenario["damaged_sectors"])
        lines.append(f"\n피해 섹터: {sectors}")

    return "\n".join(lines)
