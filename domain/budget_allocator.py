"""Budget Allocator — 행동 모드 + 사용자 성향 → 예산 집행 비율."""

import logging

from config import ACTION_MODES, BUDGET_PROFILE_MULTIPLIER, PROFILE_NAMES

logger = logging.getLogger("geolight.domain.budget")

# 시장 상황별 투자 비중 계수 (risk_score → 가용자금 중 투자 권장 비율)
MARKET_INVEST_RATIO = {
    "hold": 0.10,            # 관망: 가용자금의 10%만 투자
    "conservative_dca": 0.20, # 보수적: 20%
    "normal_dca": 0.35,       # 일반: 35%
    "rebalance": 0.30,        # 리밸런싱: 30%
    "aggressive": 0.50,       # 적극: 50%
}


def calculate_investable_amount(
    monthly_income: int,
    fixed_expenses: int,
    action_mode: str,
    risk_profile: str = "neutral",
) -> dict:
    """월 소득/지출 기반 투자 가능액 계산.

    Args:
        monthly_income: 월 소득
        fixed_expenses: 고정 지출
        action_mode: 행동 모드 키
        risk_profile: 투자 성향

    Returns:
        {
            "disposable": int,         # 가용 자금 (소득 - 지출)
            "invest_ratio": float,     # 투자 권장 비율
            "invest_amount": int,      # 투자 권장액
            "savings_amount": int,     # 저축 권장액
            "emergency_amount": int,   # 비상금 적립 권장액
        }
    """
    disposable = max(monthly_income - fixed_expenses, 0)

    # 시장 상황 기반 투자 비율
    base_ratio = MARKET_INVEST_RATIO.get(action_mode, 0.35)

    # 성향 계수 적용
    multiplier = BUDGET_PROFILE_MULTIPLIER.get(risk_profile, 1.0)
    invest_ratio = min(base_ratio * multiplier, 0.70)  # 최대 70%

    invest_amount = int(disposable * invest_ratio)
    remaining = disposable - invest_amount

    # 나머지: 비상금 30%, 저축 70%
    emergency_amount = int(remaining * 0.3)
    savings_amount = remaining - emergency_amount

    return {
        "disposable": disposable,
        "invest_ratio": invest_ratio,
        "invest_amount": invest_amount,
        "savings_amount": savings_amount,
        "emergency_amount": emergency_amount,
    }


def calculate_budget(
    action_mode: str,
    monthly_budget: int = 0,
    risk_profile: str = "neutral",
) -> dict:
    """투자 예산 집행 비율 계산.

    Args:
        action_mode: ACTION_MODES 키 (hold, conservative_dca, ...)
        monthly_budget: 월 투자 가능 금액 (0이면 비율만 반환)
        risk_profile: conservative / neutral / aggressive

    Returns:
        {
            "mode_name": str,
            "base_ratio": (low, high),
            "adjusted_ratio": (low, high),
            "monthly_budget": int,
            "execute_amount": (low, high),
            "reserve_amount": int,
            "explanation": str,
        }
    """
    mode = ACTION_MODES.get(action_mode, ACTION_MODES["normal_dca"])
    base_low, base_high = mode["budget_ratio"]

    # 성향 계수 적용
    multiplier = BUDGET_PROFILE_MULTIPLIER.get(risk_profile, 1.0)
    adj_low = min(int(base_low * multiplier), 100)
    adj_high = min(int(base_high * multiplier), 100)

    # 금액 계산
    exec_low = int(monthly_budget * adj_low / 100) if monthly_budget else 0
    exec_high = int(monthly_budget * adj_high / 100) if monthly_budget else 0
    reserve = monthly_budget - exec_high if monthly_budget else 0

    # 설명 생성
    profile_name = PROFILE_NAMES.get(risk_profile, risk_profile)

    if monthly_budget:
        explanation = (
            f"투자 성향 '{profile_name}' 기준, "
            f"이번 달 {monthly_budget:,}원 중 "
            f"{exec_low:,}~{exec_high:,}원 집행 권장"
        )
    else:
        explanation = (
            f"투자 성향 '{profile_name}' 기준, "
            f"투자예산의 {adj_low}~{adj_high}% 집행 권장"
        )

    return {
        "mode_name": mode["name"],
        "base_ratio": (base_low, base_high),
        "adjusted_ratio": (adj_low, adj_high),
        "monthly_budget": monthly_budget,
        "execute_amount": (exec_low, exec_high),
        "reserve_amount": max(reserve, 0),
        "explanation": explanation,
    }


def format_budget_card(budget: dict, action_result: dict,
                       investable: dict = None) -> str:
    """예산 배분 결과를 텔레그램 메시지로 포맷."""
    from config import SECTOR_STOCKS

    mode = action_result["mode"]
    focus_sectors = action_result.get("focus_sectors", [])
    lines = [
        "💰 이번 달 예산 가이드",
        f"{mode['emoji']} {mode['name']}",
    ]

    if budget["monthly_budget"]:
        low, high = budget["execute_amount"]
        reserve = budget["reserve_amount"]
        if action_result["mode_key"] == "hold":
            summary = "이번 달은 신규 매수보다 현금 유지 비중이 높습니다."
        else:
            summary = f"이번 달 투자예산 {budget['monthly_budget']:,}원 중 {low:,}~{high:,}원만 집행하세요."
            if reserve > 0:
                summary += f" 나머지 {reserve:,}원은 대기 자금입니다."
    else:
        adj_low, adj_high = budget["adjusted_ratio"]
        summary = f"이번 달 투자예산의 {adj_low}~{adj_high}%만 집행하는 기준입니다."
    lines.extend(["한줄 요약: " + summary, ""])

    if investable and investable.get("disposable", 0) > 0:
        lines.extend([
            "월급 배분",
            "-" * 25,
            f"  가용 자금: {investable['disposable']:,}원",
            f"  투자: {investable['invest_amount']:,}원 ({investable['invest_ratio']*100:.0f}%)",
            f"  저축: {investable['savings_amount']:,}원",
            f"  비상금: {investable['emergency_amount']:,}원",
            "",
        ])

    if budget["monthly_budget"]:
        lines.extend([
            "이번 달 실행안",
            "-" * 25,
            f"  투자 예산: {budget['monthly_budget']:,}원",
            f"  집행 금액: {low:,}~{high:,}원",
            f"  대기 자금: {reserve:,}원",
            "",
        ])

        if focus_sectors and action_result["mode_key"] != "hold":
            n_sectors = len(focus_sectors)
            sector_low = low // n_sectors
            sector_high = high // n_sectors

            lines.append("섹터별 실행안")
            lines.append("-" * 25)
            for sector in focus_sectors:
                stocks = SECTOR_STOCKS.get(sector, [])
                stock_names = ", ".join(s["name"] for s in stocks[:2]) if stocks else ""
                lines.append(f"  {sector}: {sector_low:,}~{sector_high:,}원")
                if stock_names:
                    lines.append(f"    예시 종목: {stock_names}")
            lines.append("")
            lines.append("메모: 확신이 높아도 한 섹터 몰빵보다는 분할이 안전합니다.")
        elif action_result["mode_key"] == "hold":
            lines.append("현재는 관망 구간입니다.")
            lines.append("신규 매수보다 기존 보유 관리와 현금 비중 확보가 우선입니다.")

        exit_signals = list(action_result.get("exit_signals", []))
        if exit_signals:
            lines.extend([
                "",
                "회수 기준",
                "-" * 25,
            ])
            for idx, signal in enumerate(exit_signals[:3], 1):
                lines.append(f"  {idx}. {signal}")
    else:
        adj_low, adj_high = budget["adjusted_ratio"]
        lines.extend([
            "이번 달 실행안",
            "-" * 25,
            f"  집행 비율: {adj_low}~{adj_high}%",
            "",
            "다음 단계",
            "-" * 25,
            "  /profile 200만",
            "  월 투자 예산을 넣으면 금액 단위로 바로 계산됩니다.",
        ])

    if not investable or investable.get("disposable", 0) == 0:
        if budget["monthly_budget"]:
            lines.extend([
                "",
                "다음 단계",
                "-" * 25,
                "  /profile 소득 500만 지출 300만",
                "  월급 배분까지 함께 계산할 수 있습니다.",
            ])

    return "\n".join(lines)
