"""Portfolio — 보유 종목(포지션) 관리 + 시나리오 연동."""

import logging
from typing import Optional

from config import SECTOR_STOCKS
from storage.db import (
    get_positions,
    get_position_by_name,
    upsert_position,
    delete_position,
)

logger = logging.getLogger("geolight.domain.portfolio")

# 종목코드 → 섹터 역매핑 (SECTOR_STOCKS 기반)
_CODE_TO_SECTORS: dict[str, list[str]] = {}


def _build_code_to_sectors():
    """SECTOR_STOCKS에서 종목코드→섹터 역매핑 생성."""
    global _CODE_TO_SECTORS
    if _CODE_TO_SECTORS:
        return
    for sector, stocks in SECTOR_STOCKS.items():
        for s in stocks:
            code = s.get("code", "")
            if code:
                _CODE_TO_SECTORS.setdefault(code, []).append(sector)


def find_stock_in_sectors(name: str) -> Optional[dict]:
    """SECTOR_STOCKS에서 종목명으로 검색.

    Returns:
        {"name": str, "code": str, "sectors": list[str]} 또는 None
    """
    _build_code_to_sectors()
    name_lower = name.lower().replace(" ", "")
    for sector, stocks in SECTOR_STOCKS.items():
        for s in stocks:
            if not s.get("code"):
                continue
            s_name = s["name"].lower().replace(" ", "")
            if name_lower in s_name or s_name in name_lower:
                return {
                    "name": s["name"],
                    "code": s["code"],
                    "sectors": _CODE_TO_SECTORS.get(s["code"], [sector]),
                }
    return None


def add_position(
    user_id: int,
    stock_name: str,
    avg_price: int,
    quantity: int,
    memo: str = "",
) -> dict:
    """포지션 추가. 종목명 매칭 시 코드/섹터 자동 연결.

    Returns:
        {"stock_name": str, "stock_code": str, "sector": str,
         "avg_price": int, "quantity": int, "total": int}
    """
    matched = find_stock_in_sectors(stock_name)
    if matched:
        stock_code = matched["code"]
        resolved_name = matched["name"]
        sector = matched["sectors"][0] if matched["sectors"] else ""
    else:
        # 매칭 안 되는 종목도 허용 (사용자 직접 입력)
        stock_code = ""
        resolved_name = stock_name
        sector = ""

    upsert_position(
        telegram_user_id=user_id,
        stock_code=stock_code or resolved_name,  # 코드 없으면 이름을 키로
        stock_name=resolved_name,
        avg_price=avg_price,
        quantity=quantity,
        sector=sector,
        memo=memo,
    )

    total = avg_price * quantity
    logger.info("포지션 추가: user=%d, %s %d주 @%d (총 %s원)",
                user_id, resolved_name, quantity, avg_price, f"{total:,}")

    return {
        "stock_name": resolved_name,
        "stock_code": stock_code,
        "sector": sector,
        "avg_price": avg_price,
        "quantity": quantity,
        "total": total,
    }


def remove_position(user_id: int, stock_name: str) -> bool:
    """포지션 삭제. 종목명으로 검색 후 삭제."""
    # 1) 정확한 이름으로 DB 검색
    pos = get_position_by_name(user_id, stock_name)
    if pos:
        return delete_position(user_id, pos["stock_code"])

    # 2) SECTOR_STOCKS에서 매칭 시도
    matched = find_stock_in_sectors(stock_name)
    if matched:
        return delete_position(user_id, matched["code"])

    return False


def get_user_positions(user_id: int) -> list[dict]:
    """사용자의 전체 포지션 목록."""
    return get_positions(user_id)


def get_portfolio_summary(user_id: int) -> dict:
    """포트폴리오 요약.

    Returns:
        {
            "positions": list[dict],
            "total_invested": int,
            "sector_weights": dict[str, int],  # 섹터별 투자금액
            "count": int,
        }
    """
    positions = get_positions(user_id)
    total = 0
    sector_weights: dict[str, int] = {}

    for pos in positions:
        amount = pos["avg_price"] * pos["quantity"]
        total += amount
        sector = pos.get("sector", "") or "미분류"
        sector_weights[sector] = sector_weights.get(sector, 0) + amount

    return {
        "positions": positions,
        "total_invested": total,
        "sector_weights": sector_weights,
        "count": len(positions),
    }


def analyze_portfolio_vs_scenario(
    user_id: int,
    beneficiary_sectors: list[str],
    damaged_sectors: list[str],
) -> dict:
    """포트폴리오 vs 시나리오 교차 분석.

    Returns:
        {
            "benefited": list[dict],   # 수혜 포지션
            "at_risk": list[dict],     # 위험 포지션
            "neutral": list[dict],     # 무관 포지션
        }
    """
    positions = get_positions(user_id)
    benefited = []
    at_risk = []
    neutral = []

    _build_code_to_sectors()

    for pos in positions:
        code = pos["stock_code"]
        pos_sectors = set(_CODE_TO_SECTORS.get(code, []))
        if pos.get("sector"):
            pos_sectors.add(pos["sector"])

        amount = pos["avg_price"] * pos["quantity"]
        info = {
            "name": pos["stock_name"],
            "amount": amount,
            "quantity": pos["quantity"],
            "sectors": list(pos_sectors),
        }

        is_benefited = bool(pos_sectors & set(beneficiary_sectors))
        is_at_risk = bool(pos_sectors & set(damaged_sectors))

        if is_benefited and not is_at_risk:
            benefited.append(info)
        elif is_at_risk:
            at_risk.append(info)
        else:
            neutral.append(info)

    return {
        "benefited": benefited,
        "at_risk": at_risk,
        "neutral": neutral,
    }


def format_portfolio(user_id: int) -> str:
    """포트폴리오 목록을 텔레그램 메시지로 포맷."""
    summary = get_portfolio_summary(user_id)

    if not summary["positions"]:
        sep = "-" * 25
        return (
            "보유 종목이 없습니다.\n\n"
            f"종목 추가 방법\n{sep}\n"
            "/portfolio 삼성전자 70000 10\n"
            "  → 삼성전자 평단가 70,000원 10주\n\n"
            "/portfolio 현대차 200000 5\n"
            "  → 현대차 평단가 200,000원 5주"
        )

    lines = [
        "내 포트폴리오",
        f"총 {summary['count']}종목, 투자원금 {summary['total_invested']:,}원",
        "",
    ]

    # 종목별 표시
    lines.append("보유 종목")
    lines.append("-" * 25)
    for pos in summary["positions"]:
        amount = pos["avg_price"] * pos["quantity"]
        sector_tag = f" [{pos['sector']}]" if pos.get("sector") else ""
        lines.append(
            f"  {pos['stock_name']}{sector_tag}"
        )
        lines.append(
            f"    {pos['quantity']}주 × {pos['avg_price']:,}원 = {amount:,}원"
        )

    # 섹터별 비중
    if summary["sector_weights"]:
        lines.extend(["", "섹터별 비중", "-" * 25])
        sorted_sectors = sorted(
            summary["sector_weights"].items(),
            key=lambda x: x[1],
            reverse=True,
        )
        for sector, amount in sorted_sectors:
            pct = amount / summary["total_invested"] * 100 if summary["total_invested"] else 0
            lines.append(f"  {sector}: {amount:,}원 ({pct:.0f}%)")

    lines.extend([
        "",
        "관리 명령",
        "-" * 25,
        "/portfolio 종목명 평단가 수량  → 추가/수정",
        "/portfolio 삭제 종목명  → 삭제",
    ])

    return "\n".join(lines)


def format_portfolio_action_advice(
    analysis: dict,
    mode_key: str,
) -> str:
    """포트폴리오 기반 행동 조언을 포맷."""
    lines = []

    if analysis["benefited"]:
        lines.append("내 종목 중 수혜")
        lines.append("-" * 25)
        for pos in analysis["benefited"]:
            lines.append(f"  {pos['name']}: {pos['amount']:,}원")
        lines.append("")

    if analysis["at_risk"]:
        lines.append("내 종목 중 주의")
        lines.append("-" * 25)
        for pos in analysis["at_risk"]:
            lines.append(f"  {pos['name']}: {pos['amount']:,}원")

        if mode_key == "hold":
            lines.append("  → 추가 매수 보류, 비중 축소 검토")
        else:
            lines.append("  → 비중이 크면 일부 축소 고려")
        lines.append("")

    if not analysis["benefited"] and not analysis["at_risk"]:
        lines.append("내 종목은 현재 시나리오와 직접 연관이 적습니다.")
        lines.append("")

    return "\n".join(lines)
