"""GeoLight 진입점 — 스케줄러 + 텔레그램 봇."""

import sys
import os
import asyncio
import logging
import time
from datetime import datetime

import schedule

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(__file__))

from infra.logging_config import setup_logging
from storage.db import init_db
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    NEWS_INTERVAL_MIN,
    PRICE_INTERVAL_MIN,
    SCENARIO_INTERVAL_MIN,
)

logger = setup_logging()


# ── 스케줄 작업 ──────────────────────────────────────────

def job_collect_news():
    """뉴스 수집 + 이벤트 분류 + DB 저장."""
    try:
        from data.news_collector import collect_all_news
        from domain.event_classifier import classify_by_keywords
        from domain.sector_mapper import translate_news_to_sectors
        from storage.db import insert_news, insert_event

        logger.info("=== 뉴스 수집 시작 ===")
        articles = collect_all_news()

        new_count = 0
        event_count = 0
        for art in articles:
            inserted = insert_news(
                source=art["source"],
                title=art["title"],
                url=art.get("url", ""),
                summary=art.get("summary", ""),
                published_at=art.get("published_at", ""),
            )
            if not inserted:
                continue
            new_count += 1

            # 이벤트 분류 — 키워드 매칭만 (LLM 호출 안 함 = 빠름)
            text = f"{art['title']} {art.get('summary', '')}"
            events = classify_by_keywords(text)
            if events:
                top_event = events[0]
                mappings = translate_news_to_sectors([top_event])
                sectors = mappings[0] if mappings else {}
                insert_event(
                    event_type=top_event["event_type"],
                    title=art["title"],
                    detail=art.get("summary", ""),
                    sectors=sectors,
                )
                event_count += 1

        logger.info("뉴스 수집 완료: 신규 %d건, 이벤트 %d건", new_count, event_count)

    except Exception as e:
        logger.error("뉴스 수집 실패: %s", e, exc_info=True)


def job_check_prices():
    """가격 체크 + 임계치 알림."""
    try:
        from data.price_fetcher import fetch_all_prices
        from domain.threshold_monitor import check_all_thresholds

        prices = fetch_all_prices()
        if not prices:
            logger.warning("가격 데이터 없음")
            return

        alerts = check_all_thresholds(prices)
        if alerts:
            # 텔레그램 알림 발송
            _send_alerts_sync(alerts)

    except Exception as e:
        logger.error("가격 체크 실패: %s", e, exc_info=True)


def job_update_scenarios():
    """시나리오 상태 업데이트."""
    try:
        from data.price_fetcher import fetch_all_prices
        from domain.scenario_engine import find_best_scenario

        prices = fetch_all_prices()
        indicators = {}
        for ind, p in prices.items():
            indicators[f"{ind}_change_pct"] = p["change_pct"]
            indicators[ind] = p["value"]

        best = find_best_scenario(indicators)
        if best and best["score"] > 0.5:
            logger.info("현재 시나리오: %s (%.0f%%)", best["name"], best["score"] * 100)

    except Exception as e:
        logger.error("시나리오 업데이트 실패: %s", e, exc_info=True)


def job_morning_briefing():
    """조간 브리핑 — 매일 08:30 자동 발송."""
    try:
        from data.price_fetcher import fetch_all_prices
        from domain.scenario_engine import find_best_scenario
        from domain.action_engine import get_action_result, format_action_card
        from domain.budget_allocator import calculate_budget
        from storage.db import get_recent_events
        from config import INDICATOR_DISPLAY_NAMES

        logger.info("=== 조간 브리핑 생성 ===")

        prices = fetch_all_prices()
        if not prices:
            logger.warning("조간 브리핑: 가격 데이터 없음")
            return

        indicators = {}
        for ind, p in prices.items():
            indicators[f"{ind}_change_pct"] = p["change_pct"]
            indicators[ind] = p["value"]

        scenario = find_best_scenario(indicators)
        events = get_recent_events(limit=20)
        result = get_action_result(indicators, scenario, events)

        budget = calculate_budget(
            action_mode=result["mode_key"],
            monthly_budget=0,
            risk_profile="neutral",
        )

        lines = [
            f"GeoLight 조간 브리핑 — {datetime.now().strftime('%m/%d %H:%M')}",
            "",
        ]

        # 핵심 지표
        lines.append("주요 지표")
        lines.append("-" * 25)
        for ind, p in prices.items():
            name = INDICATOR_DISPLAY_NAMES.get(ind, ind)
            lines.append(f"  {name}: {p['value']:,.2f} ({p['change_pct']:+.2f}%)")
        lines.append("")

        # 행동 카드
        lines.append(format_action_card(result, budget))

        text = "\n".join(lines)
        _send_alert_sync_simple(text)
        logger.info("조간 브리핑 발송 완료")

    except Exception as e:
        logger.error("조간 브리핑 실패: %s", e, exc_info=True)


def job_healthcheck():
    """헬스체크 — 매일 09:00."""
    try:
        msg = f"GeoLight 헬스체크 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n서비스 정상 동작 중"
        _send_alert_sync_simple(msg)
        logger.info("헬스체크 완료")
    except Exception as e:
        logger.error("헬스체크 실패: %s", e, exc_info=True)


# ── 동기 텔레그램 발송 헬퍼 ───────────────────────────────

def _send_alerts_sync(alerts: list[dict]):
    """스케줄러에서 동기적으로 텔레그램 알림 발송."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    import requests as req
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    for alert in alerts:
        try:
            req.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": alert["message"],
            }, timeout=10)
        except Exception as e:
            logger.warning("텔레그램 알림 전송 실패: %s", e)


def _send_alert_sync_simple(text: str):
    """단순 텍스트 메시지 동기 발송."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    import requests as req
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        req.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
        }, timeout=10)
    except Exception as e:
        logger.warning("텔레그램 메시지 전송 실패: %s", e)


# ── 메인 ─────────────────────────────────────────────────

def run_scheduler():
    """스케줄러 실행 (봇과 별도 스레드)."""
    logger.info("스케줄러 등록 중...")

    # 스케줄 먼저 등록 (봇이 즉시 응답할 수 있도록)
    # 스케줄 등록
    schedule.every(NEWS_INTERVAL_MIN).minutes.do(job_collect_news)
    schedule.every(PRICE_INTERVAL_MIN).minutes.do(job_check_prices)
    schedule.every(SCENARIO_INTERVAL_MIN).minutes.do(job_update_scenarios)
    schedule.every().day.at("08:30").do(job_morning_briefing)
    schedule.every().day.at("09:00").do(job_healthcheck)

    for job in schedule.get_jobs():
        logger.info("  %s", job)

    logger.info("스케줄러 시작 — 초기 수집 실행")

    # 즉시 1회 실행 (스케줄 등록 후에 실행하여 봇이 먼저 준비됨)
    job_check_prices()
    job_update_scenarios()
    job_collect_news()  # 가장 느린 작업은 마지막

    logger.info("초기 수집 완료 — 주기적 실행 시작")
    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    """메인 진입점."""
    logger.info("=" * 50)
    logger.info("GeoLight 시작")
    logger.info("=" * 50)

    # DB 초기화
    init_db()

    # 텔레그램 봇 시작
    from api.telegram_bot import create_bot_app

    bot_app = create_bot_app()

    if bot_app:
        # 스케줄러를 별도 스레드에서 실행
        import threading
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

        # 봇 폴링 실행 (메인 스레드)
        logger.info("텔레그램 봇 폴링 시작")
        bot_app.run_polling(drop_pending_updates=True)
    else:
        # 봇 없이 스케줄러만 실행
        logger.info("텔레그램 봇 없이 스케줄러만 실행")
        run_scheduler()


if __name__ == "__main__":
    main()
