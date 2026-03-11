"""시나리오 기반 투자 지도 — 현재 지표로 시나리오 매칭."""

import logging
from typing import Optional

from config import (
    INDICATOR_ALIASES,
    INDICATOR_DISPLAY_NAMES,
    INDICATOR_MEANINGS,
    SCENARIOS,
    SECTOR_STOCKS,
)

logger = logging.getLogger("geolight.domain.scenario")

_INDICATOR_LABEL_OVERRIDES = {
    "oil_change_pct": "유가 변화",
    "usd_krw_change_pct": "USD/KRW 변화",
    "kospi_change_pct": "KOSPI 변화",
}


def _resolve_indicator_value(indicators: dict, ind_key: str) -> Optional[float]:
    """시나리오 지표 키를 실제 입력값으로 해석한다.

    과거 설정과 현재 입력 포맷이 공존하므로 별칭을 흡수한다.
    """
    value = indicators.get(ind_key)
    if value is not None:
        return value

    alias_keys = INDICATOR_ALIASES.get(ind_key, [])
    alias_values = [indicators.get(alias_key) for alias_key in alias_keys]
    alias_values = [v for v in alias_values if v is not None]
    if alias_values:
        # 복수 소스가 한 개의 시나리오 축을 대표할 때 평균값으로 비교한다.
        return sum(alias_values) / len(alias_values)

    return None


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
        value = _resolve_indicator_value(indicators, ind_key)
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
        "meaning": scenario.get("meaning", ""),
        "exit_signals": list(scenario.get("exit_signals", [])),
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


def _format_matched_condition(condition: str) -> str:
    """내부 조건 문자열을 사용자 친화 문구로 변환한다."""
    if "=" not in condition:
        return condition

    ind_key, rest = condition.split("=", 1)
    label = _INDICATOR_LABEL_OVERRIDES.get(
        ind_key, INDICATOR_DISPLAY_NAMES.get(ind_key, ind_key)
    )
    return f"{label}: {rest}"


def _extract_indicator_key(condition: str) -> str:
    if "=" not in condition:
        return condition
    return condition.split("=", 1)[0]


def format_scenario_card(scenario: dict) -> str:
    """시나리오를 텔레그램용 카드 형식으로 포맷."""
    if not scenario:
        return "현재 매칭되는 시나리오가 없습니다."

    score_pct = scenario["score"] * 100
    if score_pct >= 80:
        stance = "현재 가장 강한 시나리오입니다."
    elif score_pct >= 50:
        stance = "현재 우세한 흐름으로 볼 수 있습니다."
    else:
        stance = "힌트 수준이며 단정하기는 이릅니다."

    lines = [
        f"시나리오: {scenario['name']}",
        f"한줄 해석: {stance}",
        f"설명: {scenario['description']}",
        f"매칭 점수: {score_pct:.0f}%",
    ]

    if scenario.get("meaning"):
        lines.extend([
            "",
            "이 시나리오가 뜻하는 것",
            "-" * 25,
            f"  {scenario['meaning']}",
        ])

    if scenario.get("matched"):
        lines.append("")
        lines.append("지금 이렇게 보는 이유")
        lines.append("-" * 25)
        for item in scenario["matched"][:3]:
            lines.append(f"  - {_format_matched_condition(item)}")

        meaning_keys = []
        for item in scenario["matched"][:3]:
            key = _extract_indicator_key(item)
            if key not in meaning_keys:
                meaning_keys.append(key)

        meaning_lines = [
            f"  - {_INDICATOR_LABEL_OVERRIDES.get(key, INDICATOR_DISPLAY_NAMES.get(key, key))}: {INDICATOR_MEANINGS[key]}"
            for key in meaning_keys
            if key in INDICATOR_MEANINGS
        ]
        if meaning_lines:
            lines.append("")
            lines.append("지표 의미")
            lines.append("-" * 25)
            lines.extend(meaning_lines)

    if scenario.get("beneficiary_sectors"):
        sectors = ", ".join(scenario["beneficiary_sectors"][:3])
        lines.append("")
        lines.append(f"볼 섹터: {sectors}")
        for sector in scenario["beneficiary_sectors"][:3]:
            stocks = SECTOR_STOCKS.get(sector, [])
            if stocks:
                names = ", ".join(s["name"] for s in stocks[:2])
                lines.append(f"  {sector}: {names}")

    if scenario.get("damaged_sectors"):
        sectors = ", ".join(scenario["damaged_sectors"][:3])
        lines.append("")
        lines.append(f"피할 섹터: {sectors}")

    return "\n".join(lines)
