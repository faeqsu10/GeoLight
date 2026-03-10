"""임계치 모니터링 — 가격 급변 감지 + 쿨다운."""

import logging
import time
from typing import Optional

from config import THRESHOLDS
from storage.db import get_last_alert, insert_alert, insert_price_snapshot

logger = logging.getLogger("geolight.domain.threshold")

# 마지막 알림 시각 (in-memory 쿨다운)
_last_alert_time: dict[str, float] = {}


def check_threshold(indicator: str, value: float, prev_value: float,
                    change_pct: float) -> Optional[dict]:
    """임계치 돌파 여부 확인.

    Returns:
        돌파 시: {"indicator", "value", "prev_value", "change_pct", "threshold_pct", "message"}
        미돌파: None
    """
    threshold_config = THRESHOLDS.get(indicator)
    if not threshold_config:
        return None

    threshold_pct = threshold_config["pct"]
    cooldown_min = threshold_config["cooldown_min"]

    # 임계치 미돌파
    if abs(change_pct) < threshold_pct:
        return None

    # 쿨다운 체크 (in-memory)
    now = time.time()
    last_time = _last_alert_time.get(indicator, 0)
    if now - last_time < cooldown_min * 60:
        logger.debug("[%s] 쿨다운 중 (%.0f분 남음)",
                     indicator, cooldown_min - (now - last_time) / 60)
        return None

    # DB 쿨다운 체크 (프로세스 재시작 대비)
    last_db_alert = get_last_alert(indicator)
    if last_db_alert:
        from datetime import datetime
        try:
            alert_time = datetime.strptime(last_db_alert["created_at"], "%Y-%m-%d %H:%M:%S")
            elapsed_min = (datetime.now() - alert_time).total_seconds() / 60
            if elapsed_min < cooldown_min:
                logger.debug("[%s] DB 쿨다운 중 (%.0f분 남음)",
                             indicator, cooldown_min - elapsed_min)
                return None
        except (ValueError, TypeError):
            pass

    # 임계치 돌파!
    direction = "급등" if change_pct > 0 else "급락"
    indicator_names = {
        "oil_wti": "WTI 유가",
        "oil_brent": "브렌트 유가",
        "usd_krw": "USD/KRW 환율",
        "vix": "VIX 공포지수",
        "kospi": "KOSPI",
    }
    name = indicator_names.get(indicator, indicator)
    message = (
        f"[임계치 돌파] {name} {direction}\n"
        f"현재: {value:,.2f} (전일 대비 {change_pct:+.2f}%)\n"
        f"기준: ±{threshold_pct}%"
    )

    # 쿨다운 갱신
    _last_alert_time[indicator] = now

    # DB 기록
    insert_alert("threshold", indicator, value, change_pct, message)
    insert_price_snapshot(indicator, value, prev_value, change_pct)

    logger.info("임계치 돌파: %s %+.2f%%", indicator, change_pct)

    return {
        "indicator": indicator,
        "name": name,
        "value": value,
        "prev_value": prev_value,
        "change_pct": change_pct,
        "threshold_pct": threshold_pct,
        "message": message,
    }


def check_all_thresholds(prices: dict[str, dict]) -> list[dict]:
    """모든 가격 데이터에 대해 임계치 확인."""
    alerts = []
    for indicator, price_data in prices.items():
        result = check_threshold(
            indicator,
            price_data["value"],
            price_data["prev_value"],
            price_data["change_pct"],
        )
        if result:
            alerts.append(result)
    return alerts
