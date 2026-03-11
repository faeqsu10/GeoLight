"""Action Engine — 시장 상태를 행동 모드로 번역."""

import json
import logging
import threading
import time
from datetime import date
from typing import Optional

from config import (
    ACTION_AGGRESSIVE_SCENARIOS,
    ACTION_EVENT_BUCKETS,
    ACTION_MODE_FLOW,
    ACTION_URGENT_RULES,
    ACTION_RISK_RULES,
    ACTION_SCENARIO_SCORES,
    ACTION_MODES,
    ACTION_COOLDOWN_HOURS,
    SECTOR_STOCKS,
)

logger = logging.getLogger("geolight.domain.action")

# 마지막 판정 결과 캐시 (flip-flop 방지)
# 참고: 개인 전용 시스템이므로 사용자별 캐시 분리 불필요.
# 다중 사용자 전환 시 user_id 기반 캐시로 변경 필요.
_lock = threading.Lock()
_last_action: Optional[dict] = None
_last_action_time: float = 0.0
_today_result: Optional[dict] = None  # 오늘의 가이드 캐시
_today_date: Optional[str] = None     # 캐시 날짜


def _is_urgent(indicators: dict) -> bool:
    """급변 조건 감지 — 캐시 무시하고 재계산 필요 여부."""
    for rule in ACTION_URGENT_RULES:
        value = indicators.get(rule["indicator"])
        if value is None:
            continue
        compared = abs(value) if rule.get("abs") else value
        if compared >= rule["threshold"]:
            return True
    return False


def _load_last_action_from_db():
    """서버 재시작 시 DB에서 마지막 판정 복원."""
    global _last_action, _last_action_time
    try:
        from storage.db import get_last_action
        db_action = get_last_action()
        if db_action:
            mode_key = db_action["action_mode"]
            mode = ACTION_MODES.get(mode_key, ACTION_MODES["normal_dca"])
            _last_action = {
                "mode_key": mode_key,
                "mode": mode,
                "risk_score": db_action.get("risk_score", 0),
                "scenario_name": db_action.get("scenario_name", "없음"),
            }
            # created_at → timestamp 변환 (대략적)
            from datetime import datetime
            try:
                dt = datetime.strptime(db_action["created_at"], "%Y-%m-%d %H:%M:%S")
                _last_action_time = dt.timestamp()
            except (ValueError, KeyError):
                _last_action_time = time.time() - 3600  # 1시간 전으로 가정
            logger.info("DB에서 마지막 판정 복원: %s (점수: %d)",
                        mode["name"], _last_action["risk_score"])
    except Exception as e:
        logger.warning("DB 판정 복원 실패: %s", e)


def calculate_risk_score(
    indicators: dict,
    scenario: Optional[dict] = None,
    events: Optional[list] = None,
) -> tuple[int, list[str], list[str]]:
    """위험 점수 계산.

    Returns:
        (risk_score, risk_reasons, opportunity_reasons)
    """
    score = 0
    risk_reasons = []
    opp_reasons = []

    # 1) 지표 기반 점수
    for rule in ACTION_RISK_RULES:
        ind_key = rule["indicator"]
        value = indicators.get(ind_key)
        if value is None:
            continue

        condition = rule["condition"]
        threshold = rule["value"]
        matched = False

        if condition == ">=" and value >= threshold:
            matched = True
        elif condition == "<=" and value <= threshold:
            matched = True
        elif condition == ">" and value > threshold:
            matched = True
        elif condition == "<" and value < threshold:
            matched = True

        if matched:
            pts = rule["score"]
            score += pts
            reason = f"{rule['reason']} ({value:+.2f})"
            if pts > 0:
                risk_reasons.append(reason)
            else:
                opp_reasons.append(reason)

    # 2) 시나리오 기반 점수
    if scenario and scenario.get("score", 0) >= 0.3:
        scenario_key = scenario.get("key", "")
        scenario_pts = ACTION_SCENARIO_SCORES.get(scenario_key, 0)
        if scenario_pts != 0:
            score += scenario_pts
            reason = f"시나리오: {scenario.get('name', scenario_key)} ({scenario['score']*100:.0f}%)"
            if scenario_pts > 0:
                risk_reasons.append(reason)
            else:
                opp_reasons.append(reason)

    # 3) 최근 이벤트 기반 보조 점수
    if events:
        tension_types = ACTION_EVENT_BUCKETS["tension"]
        ease_types = ACTION_EVENT_BUCKETS["ease"]

        tension_count = sum(1 for e in events if e.get("event_type") in tension_types)
        ease_count = sum(1 for e in events if e.get("event_type") in ease_types)

        if tension_count >= 3:
            score += 1
            risk_reasons.append(f"위험 이벤트 다수 감지 ({tension_count}건)")
        if ease_count >= 3:
            score -= 1
            opp_reasons.append(f"완화 이벤트 다수 감지 ({ease_count}건)")

    return score, risk_reasons, opp_reasons


def determine_action_mode(
    risk_score: int,
    scenario: Optional[dict] = None,
) -> str:
    """위험 점수 → 행동 모드 키 결정."""
    # 공격적 진입: 위험 점수 1 이하 + 완화 시나리오
    if risk_score <= 1:
        if scenario and scenario.get("key") in ACTION_AGGRESSIVE_SCENARIOS:
            if scenario.get("score", 0) > 0.3:
                return "aggressive"

    # 점수 기반 모드 결정
    if risk_score >= 6:
        return "hold"
    elif risk_score >= 4:
        return "conservative_dca"
    else:
        # score <= 3 (기회 구간 포함, 음수 점수도 여기)
        return "normal_dca"


def get_action_result(
    indicators: dict,
    scenario: Optional[dict] = None,
    events: Optional[list] = None,
    user_profile: Optional[dict] = None,
) -> dict:
    """종합 행동 판단 결과 반환.

    Args:
        indicators: {"oil_wti_change_pct": float, "vix": float, ...}
        scenario: find_best_scenario() 결과
        events: get_recent_events() 결과
        user_profile: {"risk_profile": str, "monthly_budget": int}

    Returns:
        {
            "mode_key": str,
            "mode": dict (ACTION_MODES 항목),
            "risk_score": int,
            "risk_reasons": list[str],
            "opp_reasons": list[str],
            "warnings": list[str],
            "focus_sectors": list[str],
            "scenario_name": str,
            "scenario_description": str,
            "scenario_meaning": str,
            "exit_signals": list[str],
        }
    """
    global _last_action, _last_action_time, _today_result, _today_date

    with _lock:
        # DB fallback: 서버 재시작 후 첫 호출 시 마지막 판정 복원
        if _last_action is None:
            _load_last_action_from_db()

        # 오늘의 가이드 캐싱: 같은 날 + 급변 아니면 캐시 반환
        today = date.today().isoformat()
        if (_today_date == today and _today_result is not None
                and not _is_urgent(indicators)):
            logger.info("오늘의 가이드 캐시 반환 (급변 없음)")
            return _today_result

    risk_score, risk_reasons, opp_reasons = calculate_risk_score(
        indicators, scenario, events
    )
    mode_key = determine_action_mode(risk_score, scenario)

    # 쿨다운: 이전 판정과 비교하여 급격한 변동 억제
    now = time.time()
    if _last_action and (now - _last_action_time) < ACTION_COOLDOWN_HOURS * 3600:
        prev_key = _last_action.get("mode_key")
        if prev_key and prev_key != mode_key:
            # 2단계 이상 점프 방지
            if prev_key in ACTION_MODE_FLOW and mode_key in ACTION_MODE_FLOW:
                prev_idx = ACTION_MODE_FLOW.index(prev_key)
                new_idx = ACTION_MODE_FLOW.index(mode_key)
                if abs(prev_idx - new_idx) > 1:
                    # 중간 단계로 제한
                    mid_idx = prev_idx + (1 if new_idx > prev_idx else -1)
                    original_mode = ACTION_MODES.get(mode_key, {}).get("name", mode_key)
                    mode_key = ACTION_MODE_FLOW[mid_idx]
                    risk_reasons.append(
                        f"모드 전환 조정: {_last_action['mode']['name']}→{original_mode} "
                        f"요청이나, 1단계씩 이동"
                    )

    mode = ACTION_MODES.get(mode_key, ACTION_MODES["normal_dca"])

    # 경고 생성
    warnings = []
    if risk_score >= 8:
        warnings.append("극단적 위험 구간 — 신규 투자 강력 자제")
    if risk_score >= 6:
        warnings.append("추격매수 금지")
    if indicators.get("vix", 0) >= 30:
        warnings.append("VIX 공포 구간 — 변동성 매우 높음")
    if abs(indicators.get("usd_krw_change_pct", 0)) >= 2.0:
        warnings.append("환율 급변 — 외화 자산 주의")

    # 관심 섹터 (시나리오 기반)
    focus_sectors = []
    if scenario and scenario.get("beneficiary_sectors"):
        focus_sectors = scenario["beneficiary_sectors"][:5]

    result = {
        "mode_key": mode_key,
        "mode": mode,
        "risk_score": risk_score,
        "risk_reasons": risk_reasons,
        "opp_reasons": opp_reasons,
        "warnings": warnings,
        "focus_sectors": focus_sectors,
        "scenario_name": scenario.get("name", "없음") if scenario else "없음",
        "scenario_description": scenario.get("description", "") if scenario else "",
        "scenario_meaning": scenario.get("meaning", "") if scenario else "",
        "exit_signals": list(scenario.get("exit_signals", [])) if scenario else [],
    }

    # 캐시 갱신 (lock 보호)
    with _lock:
        _last_action = result
        _last_action_time = now
        _today_result = result
        _today_date = today

    # DB 기록
    try:
        from storage.db import insert_action_history
        insert_action_history(
            action_mode=mode_key,
            scenario_name=result["scenario_name"],
            risk_score=risk_score,
            reasons=risk_reasons + opp_reasons,
            warnings=warnings,
        )
    except Exception as e:
        logger.warning("행동 이력 저장 실패: %s", e)

    logger.info("행동 판단: %s (위험점수: %d)", mode["name"], risk_score)
    return result


def format_action_card(result: dict, budget: dict = None) -> str:
    """행동 판단 결과를 텔레그램 메시지로 포맷.

    Args:
        result: get_action_result() 결과
        budget: calculate_budget() 결과 (있으면 금액 포함 요약)
    """
    mode = result["mode"]

    sector_names = result.get("focus_sectors", [])[:3]
    sector_text = "·".join(sector_names)

    budget_amount_line = ""
    budget_ratio_line = ""
    if budget and budget.get("monthly_budget"):
        low, high = budget["execute_amount"]
        reserve = budget.get("reserve_amount", 0)
        budget_amount_line = f"{low:,}~{high:,}원 집행"
        if reserve > 0:
            budget_amount_line += f", {reserve:,}원 대기"
    else:
        ratio_low, ratio_high = (budget or {}).get("adjusted_ratio", mode["budget_ratio"])
        budget_ratio_line = f"예산의 {ratio_low}~{ratio_high}% 집행"

    if result["mode_key"] == "hold":
        summary = "오늘은 신규 매수보다 보유 점검과 현금 확보가 우선"
    elif budget_amount_line and sector_text:
        summary = f"{budget_amount_line}, {sector_text} 분할 접근"
    elif budget_amount_line:
        summary = budget_amount_line
    elif budget_ratio_line and sector_text:
        summary = f"{budget_ratio_line}, {sector_text} 우선"
    elif budget_ratio_line:
        summary = budget_ratio_line
    else:
        summary = mode["guide"]

    lines = [
        f"{mode['emoji']} {mode['name']}",
        f"한줄 요약: {summary}",
        f"시나리오: {result['scenario_name']} | 위험점수: {result['risk_score']}점",
        "",
    ]

    if result.get("scenario_meaning") or result.get("scenario_description"):
        lines.extend([
            "시나리오 설명",
            "-" * 25,
        ])
        if result.get("scenario_meaning"):
            lines.append(f"  {result['scenario_meaning']}")
        elif result.get("scenario_description"):
            lines.append(f"  {result['scenario_description']}")
        lines.append("")

    lines.append("오늘 할 것")
    lines.append("-" * 25)
    if result["mode_key"] == "hold":
        lines.append("  1. 신규 매수는 보류")
        lines.append("  2. 기존 보유 종목과 현금 비중만 점검")
        lines.append("  3. 아래 섹터는 매수보다 관찰 대상으로 유지")
    else:
        if budget_amount_line:
            lines.append(f"  1. 집행 범위: {budget_amount_line}")
        elif budget_ratio_line:
            lines.append(f"  1. 집행 범위: {budget_ratio_line}")
        else:
            lines.append(f"  1. 집행 기준: {mode['guide']}")

        if sector_text:
            lines.append(f"  2. 우선 섹터: {sector_text}")
        else:
            lines.append("  2. 시나리오와 무관한 추격 진입은 피하기")

        if result["mode_key"] == "aggressive":
            lines.append("  3. 한 번에 몰지 말고 2~3회로 나눠 진입")
        else:
            lines.append("  3. 나머지 자금은 현금으로 대기")
    lines.append("")

    avoid_lines = list(result.get("warnings", []))
    if not avoid_lines:
        if result["mode_key"] == "hold":
            avoid_lines.append("반등 기대만으로 성급하게 신규 진입하지 않기")
        else:
            avoid_lines.append("한 번에 전액 진입하지 않기")

    lines.append("피할 것")
    lines.append("-" * 25)
    for idx, item in enumerate(avoid_lines[:3], 1):
        lines.append(f"  {idx}. {item}")
    lines.append("")

    if result["focus_sectors"]:
        section_title = "관찰 섹터" if result["mode_key"] == "hold" else "우선 섹터"
        lines.append(section_title)
        lines.append("-" * 25)
        for sector in result["focus_sectors"]:
            stocks = SECTOR_STOCKS.get(sector, [])
            if stocks:
                names = ", ".join(s["name"] for s in stocks[:2])
                lines.append(f"  {sector}: {names}")
            else:
                lines.append(f"  {sector}")
        lines.append("")

    exit_signals = list(result.get("exit_signals", []))
    if not exit_signals:
        if result["mode_key"] == "hold":
            exit_signals = [
                "반등이 나와도 기존 위험 포지션은 한 번에 늘리지 말고 축소부터 검토합니다.",
                "현재 시나리오가 약해지지 않아도 현금 비중 확보가 우선입니다.",
            ]
        else:
            exit_signals = [
                "반대 시나리오가 우세해지면 현재 포지션을 분할로 줄입니다.",
                "단기 급등 수익분은 2~3회로 나눠 익절합니다.",
            ]

    lines.append("줄이거나 뺄 때")
    lines.append("-" * 25)
    for idx, signal in enumerate(exit_signals[:3], 1):
        lines.append(f"  {idx}. {signal}")
    lines.append("")

    factors = []
    for r in result["risk_reasons"][:2]:
        factors.append(f"  ▲ {r}")
    for r in result.get("opp_reasons", [])[:2]:
        factors.append(f"  ▽ {r}")

    if factors:
        lines.append("판단 근거")
        lines.append("-" * 25)
        lines.extend(factors)

    return "\n".join(lines)
