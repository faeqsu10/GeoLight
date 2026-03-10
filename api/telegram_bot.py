"""GeoLight 텔레그램 봇 — 명령어 처리 + 알림 발송."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_MAX_LENGTH
from data.news_collector import collect_all_news
from data.price_fetcher import fetch_all_prices
from domain.event_classifier import classify_news
from domain.sector_mapper import translate_news_to_sectors, format_sector_summary
from domain.scenario_engine import (
    find_best_scenario,
    get_all_scenarios_status,
    format_scenario_card,
)
from domain.threshold_monitor import check_all_thresholds
from domain.trend_detector import detect_hot_stocks, format_hot_stocks
from storage.db import get_recent_events

logger = logging.getLogger("geolight.api.telegram")

_app: Optional[Application] = None


# ── 메시지 분할 전송 ──────────────────────────────────────

async def _send_message(chat_id: str, text: str, context: ContextTypes.DEFAULT_TYPE):
    """4096자 제한 대응 분할 전송."""
    if len(text) <= TELEGRAM_MAX_LENGTH:
        await context.bot.send_message(chat_id=chat_id, text=text)
        return

    # 줄 단위 분할
    lines = text.split("\n")
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > TELEGRAM_MAX_LENGTH:
            if chunk:
                await context.bot.send_message(chat_id=chat_id, text=chunk)
            chunk = line
        else:
            chunk = f"{chunk}\n{line}" if chunk else line

    if chunk:
        await context.bot.send_message(chat_id=chat_id, text=chunk)


async def send_alert(text: str):
    """외부에서 호출하는 알림 발송 (스케줄러용)."""
    if not _app or not TELEGRAM_CHAT_ID:
        logger.warning("텔레그램 앱 미초기화 또는 CHAT_ID 미설정")
        return

    try:
        if len(text) <= TELEGRAM_MAX_LENGTH:
            await _app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        else:
            lines = text.split("\n")
            chunk = ""
            for line in lines:
                if len(chunk) + len(line) + 1 > TELEGRAM_MAX_LENGTH:
                    if chunk:
                        await _app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=chunk)
                    chunk = line
                else:
                    chunk = f"{chunk}\n{line}" if chunk else line
            if chunk:
                await _app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=chunk)
    except Exception as e:
        logger.warning("텔레그램 알림 발송 실패: %s", e)


# ── 명령어 핸들러 ─────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """봇 시작 메시지."""
    text = (
        "GeoLight — 시장 망원경\n"
        "해외 뉴스를 한국장 영향으로 번역합니다.\n\n"
        "명령어:\n"
        "/now — 현재 주요 이벤트 + 영향 섹터\n"
        "/scenario — 시나리오 투자 지도\n"
        "/alert — 알림 상태 확인\n"
        "/hot — 관심 급증 종목\n"
        "/help — 도움말"
    )
    await update.message.reply_text(text)


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현재 주요 이벤트 + 영향 섹터 요약."""
    await update.message.reply_text("뉴스 수집 중...")

    try:
        # 뉴스 수집 (최근 RSS만 — GDELT은 느릴 수 있음)
        from data.news_collector import fetch_all_rss
        articles = fetch_all_rss()

        if not articles:
            await update.message.reply_text("수집된 뉴스가 없습니다.")
            return

        # 상위 20개 뉴스 분류
        all_events = []
        for art in articles[:20]:
            events = classify_news(art["title"], art.get("summary", ""))
            for evt in events:
                evt["news_title"] = art["title"]
                all_events.append(evt)

        if not all_events:
            await update.message.reply_text("현재 특별한 이벤트가 감지되지 않았습니다.")
            return

        # 이벤트별 섹터 매핑
        seen_types = set()
        unique_events = []
        for evt in all_events:
            if evt["event_type"] not in seen_types:
                seen_types.add(evt["event_type"])
                unique_events.append(evt)

        mappings = translate_news_to_sectors(unique_events)

        # 포맷
        lines = ["GeoLight — 현재 이벤트 요약", "=" * 30, ""]
        for m in mappings[:5]:
            lines.append(format_sector_summary(m))
            lines.append("")

        # 가격 현황
        prices = fetch_all_prices()
        if prices:
            lines.append("주요 지표")
            lines.append("-" * 25)
            for ind, p in prices.items():
                lines.append(f"  {ind}: {p['value']:,.2f} ({p['change_pct']:+.2f}%)")

        text = "\n".join(lines)
        await _send_message(update.effective_chat.id, text, context)

    except Exception as e:
        logger.error("/now 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(f"처리 중 오류: {e}")


async def cmd_scenario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """시나리오 투자 지도."""
    try:
        prices = fetch_all_prices()
        indicators = {}
        for ind, p in prices.items():
            indicators[f"{ind}_change_pct"] = p["change_pct"]
            indicators[ind] = p["value"]

        all_scenarios = get_all_scenarios_status(indicators)
        best = find_best_scenario(indicators)

        lines = ["GeoLight — 시나리오 투자 지도", "=" * 30, ""]

        if best:
            lines.append("현재 가장 유력한 시나리오:")
            lines.append(format_scenario_card(best))
            lines.append("")

        lines.append("전체 시나리오 매칭 현황:")
        lines.append("-" * 25)
        for s in all_scenarios:
            status = "●" if s["score"] > 0 else "○"
            lines.append(f"  {status} {s['name']}: {s['score'] * 100:.0f}%")

        text = "\n".join(lines)
        await _send_message(update.effective_chat.id, text, context)

    except Exception as e:
        logger.error("/scenario 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(f"처리 중 오류: {e}")


async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """알림 상태 확인."""
    from config import THRESHOLDS

    lines = ["GeoLight — 알림 설정 상태", "=" * 30, ""]

    indicator_names = {
        "oil_wti": "WTI 유가",
        "oil_brent": "브렌트 유가",
        "usd_krw": "USD/KRW 환율",
        "vix": "VIX 공포지수",
        "kospi": "KOSPI",
    }

    for ind, cfg in THRESHOLDS.items():
        name = indicator_names.get(ind, ind)
        lines.append(f"  {name}: ±{cfg['pct']}% (쿨다운 {cfg['cooldown_min']}분)")

    lines.append("")
    lines.append("임계치 돌파 시 자동으로 알림이 발송됩니다.")

    await update.message.reply_text("\n".join(lines))


async def cmd_hot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """관심 급증 종목."""
    await update.message.reply_text("종목 데이터 조회 중...")

    try:
        data = detect_hot_stocks(top_n=15)
        text = f"GeoLight — 관심 급증 종목\n{'=' * 30}\n\n{format_hot_stocks(data)}"
        await _send_message(update.effective_chat.id, text, context)
    except Exception as e:
        logger.error("/hot 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(f"처리 중 오류: {e}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """도움말."""
    text = (
        "GeoLight 명령어 안내\n\n"
        "/now — 현재 주요 이벤트 + 영향 섹터 요약\n"
        "  해외 뉴스를 수집·분류하여 한국장 영향을 번역합니다.\n\n"
        "/scenario — 시나리오 투자 지도\n"
        "  확전/완화/쇼크 등 시나리오별 수혜·피해 섹터를 보여줍니다.\n\n"
        "/alert — 알림 설정 상태\n"
        "  유가/환율/VIX 임계치 설정을 확인합니다.\n\n"
        "/hot — 관심 급증 종목\n"
        "  거래대금 급증 + 급락 후 반등 후보를 보여줍니다.\n"
    )
    await update.message.reply_text(text)


# ── 봇 초기화 ─────────────────────────────────────────────

def create_bot_app() -> Optional[Application]:
    """텔레그램 봇 Application 생성."""
    global _app

    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN 미설정. 봇 비활성화.")
        return None

    _app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    _app.add_handler(CommandHandler("start", cmd_start))
    _app.add_handler(CommandHandler("now", cmd_now))
    _app.add_handler(CommandHandler("scenario", cmd_scenario))
    _app.add_handler(CommandHandler("alert", cmd_alert))
    _app.add_handler(CommandHandler("hot", cmd_hot))
    _app.add_handler(CommandHandler("help", cmd_help))

    logger.info("텔레그램 봇 초기화 완료")
    return _app
