"""User Profile — 텔레그램 사용자 설정 관리."""

import logging
from typing import Optional

from storage.db import get_user_profile, save_user_profile

logger = logging.getLogger("geolight.domain.profile")

VALID_PROFILES = {"conservative", "neutral", "aggressive"}
PROFILE_NAMES = {
    "conservative": "보수",
    "neutral": "중립",
    "aggressive": "공격",
}
# 한글 입력 → 영문 매핑
PROFILE_ALIASES = {
    "보수": "conservative",
    "보수적": "conservative",
    "중립": "neutral",
    "공격": "aggressive",
    "공격적": "aggressive",
}


def get_profile(telegram_user_id: int) -> dict:
    """사용자 프로필 조회. 없으면 기본값."""
    profile = get_user_profile(telegram_user_id)
    if profile:
        return profile
    return {
        "telegram_user_id": telegram_user_id,
        "risk_profile": "neutral",
        "monthly_budget": 0,
        "monthly_income": 0,
        "fixed_expenses": 0,
    }


def update_profile(
    telegram_user_id: int,
    risk_profile: Optional[str] = None,
    monthly_budget: Optional[int] = None,
    monthly_income: Optional[int] = None,
    fixed_expenses: Optional[int] = None,
) -> dict:
    """프로필 업데이트. 변경된 필드만 반영."""
    current = get_profile(telegram_user_id)

    if risk_profile:
        # 한글 → 영문 변환
        resolved = PROFILE_ALIASES.get(risk_profile, risk_profile)
        if resolved in VALID_PROFILES:
            current["risk_profile"] = resolved
        else:
            raise ValueError(
                f"잘못된 투자 성향: '{risk_profile}'. "
                f"가능한 값: 보수/중립/공격 (conservative/neutral/aggressive)"
            )

    if monthly_budget is not None:
        if monthly_budget < 0:
            raise ValueError("월 투자 예산은 0 이상이어야 합니다.")
        current["monthly_budget"] = monthly_budget

    if monthly_income is not None:
        if monthly_income < 0:
            raise ValueError("월 소득은 0 이상이어야 합니다.")
        current["monthly_income"] = monthly_income

    if fixed_expenses is not None:
        if fixed_expenses < 0:
            raise ValueError("고정 지출은 0 이상이어야 합니다.")
        current["fixed_expenses"] = fixed_expenses

    save_user_profile(
        telegram_user_id=telegram_user_id,
        risk_profile=current["risk_profile"],
        monthly_budget=current.get("monthly_budget", 0),
        monthly_income=current.get("monthly_income", 0),
        fixed_expenses=current.get("fixed_expenses", 0),
    )

    logger.info(
        "프로필 업데이트: user=%d, profile=%s, budget=%d, income=%d, expenses=%d",
        telegram_user_id, current["risk_profile"],
        current.get("monthly_budget", 0),
        current.get("monthly_income", 0),
        current.get("fixed_expenses", 0),
    )
    return current


def format_profile(profile: dict) -> str:
    """프로필을 텔레그램 메시지로 포맷."""
    name = PROFILE_NAMES.get(profile["risk_profile"], profile["risk_profile"])
    budget = profile.get("monthly_budget", 0)
    income = profile.get("monthly_income", 0)
    expenses = profile.get("fixed_expenses", 0)

    lines = [
        "내 투자 설정",
        "=" * 25,
        "",
        f"  투자 성향: {name}",
        f"  월 투자 예산: {budget:,}원" if budget else "  월 투자 예산: 미설정",
    ]

    if income:
        lines.append(f"  월 소득: {income:,}원")
        lines.append(f"  고정 지출: {expenses:,}원" if expenses else "  고정 지출: 미설정")
        disposable = max(income - expenses, 0)
        if income > expenses:
            lines.append(f"  가용 자금: {disposable:,}원")
        else:
            lines.append(f"  가용 자금: 0원 (지출이 소득 이상)")

    lines.extend([
        "",
        "설정 방법",
        "-" * 25,
        "",
        "성향 + 예산:",
        "  /profile 공격 200만",
        "",
        "소득 + 지출 (자동 예산 계산):",
        "  /profile 소득 500만 지출 300만",
        "",
        "개별 변경:",
        "  /profile 보수",
        "  /profile 200만",
        "  /profile 소득 400만",
        "  /profile 지출 250만",
    ])
    return "\n".join(lines)
