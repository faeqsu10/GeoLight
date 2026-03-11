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
from domain.ai_assistant import AIAssistant, build_market_context, markdown_to_telegram_html
import re

from domain.event_classifier import classify_news
from domain.sector_mapper import map_event_to_sectors, translate_news_to_sectors, format_sector_summary
from domain.scenario_engine import (
    find_best_scenario,
    get_all_scenarios_status,
    format_scenario_card,
)
from domain.threshold_monitor import check_all_thresholds
from domain.trend_detector import detect_hot_stocks, format_hot_stocks
from domain.action_engine import get_action_result, format_action_card
from domain.budget_allocator import calculate_budget, calculate_investable_amount, format_budget_card
from domain.user_profile import get_profile, update_profile, format_profile
from storage.db import get_recent_events

logger = logging.getLogger("geolight.api.telegram")

_app: Optional[Application] = None
_ai: Optional[AIAssistant] = None


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
        "/action — 오늘의 행동 가이드\n"
        "/budget — 예산 집행 가이드\n"
        "/profile — 내 투자 설정\n"
        "/alert — 알림 상태 확인\n"
        "/hot — 관심 급증 종목\n"
        "/ask [질문] — AI에게 시장 분석 질문\n"
        "/help — 도움말"
    )
    await update.message.reply_text(text)


async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """현재 주요 이벤트 + 영향 섹터 요약.

    빠른 응답을 위해 DB 캐시된 이벤트 우선 사용.
    DB가 비어있으면 RSS에서 소수만 빠르게 수집.
    """
    await update.message.reply_text("분석 중...")

    try:
        # 1) DB에서 최근 이벤트 조회 (빠름)
        recent_events = get_recent_events(limit=20)

        if recent_events:
            # DB 캐시 사용 — 즉시 응답
            seen_types = set()
            unique_events = []
            for evt in recent_events:
                if evt["event_type"] not in seen_types:
                    seen_types.add(evt["event_type"])
                    unique_events.append(evt)

            lines = ["GeoLight — 현재 이벤트 요약", "=" * 30, ""]

            for evt in unique_events[:5]:
                mapping = map_event_to_sectors(evt["event_type"])
                if mapping:
                    lines.append(format_sector_summary(mapping))
                    if evt.get("title"):
                        lines.append(f"  뉴스: {evt['title'][:60]}")
                    lines.append("")

        else:
            # DB 비어있으면 RSS 3개만 빠르게 수집
            from data.news_collector import fetch_rss_feed
            from config import RSS_FEEDS

            fast_feeds = ["bbc_world", "cnbc_world", "yonhap_en"]
            articles = []
            for name in fast_feeds:
                url = RSS_FEEDS.get(name)
                if url:
                    articles.extend(fetch_rss_feed(name, url)[:5])

            if not articles:
                await update.message.reply_text("수집된 뉴스가 없습니다.")
                return

            # 키워드 분류만 (LLM 호출 안 함)
            from domain.event_classifier import classify_by_keywords
            all_events = []
            for art in articles[:15]:
                events = classify_by_keywords(f"{art['title']} {art.get('summary', '')}")
                for evt in events:
                    evt["news_title"] = art["title"]
                    all_events.append(evt)

            if not all_events:
                await update.message.reply_text("현재 특별한 이벤트가 감지되지 않았습니다.")
                return

            seen_types = set()
            unique_events = []
            for evt in all_events:
                if evt["event_type"] not in seen_types:
                    seen_types.add(evt["event_type"])
                    unique_events.append(evt)

            mappings = translate_news_to_sectors(unique_events)
            lines = ["GeoLight — 현재 이벤트 요약", "=" * 30, ""]
            for m in mappings[:5]:
                lines.append(format_sector_summary(m))
                lines.append("")

        # 가격 현황 추가
        prices = fetch_all_prices()
        if prices:
            indicator_names = {
                "oil_wti": "WTI 유가",
                "oil_brent": "브렌트유",
                "usd_krw": "USD/KRW",
                "vix": "VIX",
                "kospi": "KOSPI",
            }
            lines.append("주요 지표")
            lines.append("-" * 25)
            for ind, p in prices.items():
                name = indicator_names.get(ind, ind)
                lines.append(f"  {name}: {p['value']:,.2f} ({p['change_pct']:+.2f}%)")

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
        "  거래대금 급증 + 급락 후 반등 후보를 보여줍니다.\n\n"
        "/action — 오늘의 행동 가이드\n"
        "  시장 상태를 분석하여 관망/분할매수/적극진입 등 행동 모드를 제안합니다.\n\n"
        "/budget — 예산 집행 가이드\n"
        "  행동 모드 + 투자 성향 기반 이번 달 투자 집행 비율을 보여줍니다.\n\n"
        "/profile [성향] [예산] — 내 투자 설정\n"
        "  예: /profile 공격 200만  |  /profile 보수\n\n"
        "/ask [질문] — AI 시장 분석\n"
        "  지정학·거시경제 관련 질문에 Gemini AI가 답변합니다.\n"
        "  예: /ask 중동 긴장이 한국 반도체에 미치는 영향은?\n"
    )
    await update.message.reply_text(text)


def _parse_amount(text: str) -> Optional[int]:
    """금액 문자열 파싱. '200만', '200만원', '2000000' → int. 실패 시 None.

    '만' 접미사 없는 순수 숫자는 10만 이상만 원 단위로 인정.
    그 이하는 모호하므로 거부(None 반환).
    """
    m = re.match(r"(\d+)\s*만\s*원?$", text)
    if m:
        return int(m.group(1)) * 10000
    if text.isdigit():
        val = int(text)
        if val >= 100000:  # 10만원 이상만 원 단위로 인정
            return val
    return None


def _build_indicators(prices: dict) -> dict:
    """가격 데이터를 action_engine용 indicators로 변환."""
    indicators = {}
    for ind, p in prices.items():
        indicators[f"{ind}_change_pct"] = p["change_pct"]
        indicators[ind] = p["value"]
    return indicators


async def cmd_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """오늘의 행동 가이드."""
    await update.message.reply_text("행동 모드 분석 중...")

    try:
        prices = fetch_all_prices()
        if not prices:
            await update.message.reply_text("가격 데이터를 조회할 수 없습니다.")
            return

        indicators = _build_indicators(prices)
        scenario = find_best_scenario(indicators)
        events = get_recent_events(limit=20)

        # 사용자 프로필 조회
        user_id = update.effective_user.id
        profile = get_profile(user_id)

        result = get_action_result(indicators, scenario, events, profile)
        budget = calculate_budget(
            action_mode=result["mode_key"],
            monthly_budget=profile.get("monthly_budget", 0),
            risk_profile=profile.get("risk_profile", "neutral"),
        )
        text = format_action_card(result, budget)
        await _send_message(update.effective_chat.id, text, context)

    except Exception as e:
        logger.error("/action 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(f"처리 중 오류: {e}")


async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """예산 집행 가이드."""
    try:
        prices = fetch_all_prices()
        if not prices:
            await update.message.reply_text("가격 데이터를 조회할 수 없습니다.")
            return

        indicators = _build_indicators(prices)
        scenario = find_best_scenario(indicators)
        events = get_recent_events(limit=20)

        user_id = update.effective_user.id
        profile = get_profile(user_id)

        action_result = get_action_result(indicators, scenario, events, profile)

        # 투자 예산 (직접 설정 또는 소득/지출 기반 자동 계산)
        monthly_budget = profile.get("monthly_budget", 0)
        income = profile.get("monthly_income", 0)
        expenses = profile.get("fixed_expenses", 0)
        risk_profile = profile.get("risk_profile", "neutral")

        investable = None
        auto_budget = False
        if income > 0:
            investable = calculate_investable_amount(
                monthly_income=income,
                fixed_expenses=expenses,
                action_mode=action_result["mode_key"],
                risk_profile=risk_profile,
            )
            # 예산 미설정이면 자동 계산된 투자액 사용
            if not monthly_budget:
                monthly_budget = investable["invest_amount"]
                auto_budget = True

        budget = calculate_budget(
            action_mode=action_result["mode_key"],
            monthly_budget=monthly_budget,
            # 자동 계산 예산은 이미 성향 반영됨 → 중복 적용 방지
            risk_profile="neutral" if auto_budget else risk_profile,
        )
        text = format_budget_card(budget, action_result, investable)
        await _send_message(update.effective_chat.id, text, context)

    except Exception as e:
        logger.error("/budget 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(f"처리 중 오류: {e}")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """내 투자 설정 조회/변경."""
    user_id = update.effective_user.id
    args = context.args or []

    if not args:
        # 인자 없으면 현재 프로필 표시
        profile = get_profile(user_id)
        text = format_profile(profile)
        await update.message.reply_text(text)
        return

    # 인자 파싱: /profile [성향] [예산] [소득 X만] [지출 X만]
    risk_profile = None
    monthly_budget = None
    monthly_income = None
    fixed_expenses = None

    i = 0
    while i < len(args):
        arg = args[i]

        # "소득" 키워드 → 다음 인자가 금액
        if arg == "소득" and i + 1 < len(args):
            parsed = _parse_amount(args[i + 1])
            if parsed is not None:
                monthly_income = parsed
                i += 2
                continue
            # 파싱 실패: "소득" 키워드 무시하고 다음으로
            i += 1
            continue

        # "지출" 키워드 → 다음 인자가 금액
        if arg == "지출" and i + 1 < len(args):
            parsed = _parse_amount(args[i + 1])
            if parsed is not None:
                fixed_expenses = parsed
                i += 2
                continue
            i += 1
            continue

        # 투자 성향 체크
        if arg in ("보수", "보수적", "중립", "공격", "공격적",
                    "conservative", "neutral", "aggressive"):
            risk_profile = arg
            i += 1
            continue

        # 예산 파싱: "200만", "200만원", "2000000"
        parsed = _parse_amount(arg)
        if parsed is not None:
            monthly_budget = parsed
            i += 1
            continue

        i += 1

    if (risk_profile is None and monthly_budget is None
            and monthly_income is None and fixed_expenses is None):
        await update.message.reply_text(
            "설정 형식이 올바르지 않습니다.\n\n"
            "예: /profile 공격 200만\n"
            "예: /profile 소득 500만 지출 300만\n"
            "예: /profile 보수"
        )
        return

    try:
        profile = update_profile(
            user_id, risk_profile, monthly_budget,
            monthly_income, fixed_expenses,
        )
        text = format_profile(profile)
        await update.message.reply_text(f"설정이 저장되었습니다.\n\n{text}")
    except ValueError as e:
        await update.message.reply_text(str(e))
    except Exception as e:
        logger.error("/profile 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(f"처리 중 오류: {e}")


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI에게 시장 분석 질문."""
    global _ai

    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.message.reply_text(
            "질문을 입력해주세요.\n예: /ask 중동 긴장이 한국 반도체에 미치는 영향은?"
        )
        return

    if not _ai:
        _ai = AIAssistant()

    remaining = _ai.remaining_today
    await update.message.reply_text(f"AI 분석 중... (남은 횟수: {remaining})")

    try:
        market_ctx = build_market_context()
        answer = _ai.ask(question, context=market_ctx)

        await _send_message(
            update.effective_chat.id,
            answer,
            context,
        )
    except Exception as e:
        logger.error("/ask 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(f"AI 처리 오류: {e}")


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
    _app.add_handler(CommandHandler("action", cmd_action))
    _app.add_handler(CommandHandler("budget", cmd_budget))
    _app.add_handler(CommandHandler("profile", cmd_profile))
    _app.add_handler(CommandHandler("ask", cmd_ask))
    _app.add_handler(CommandHandler("help", cmd_help))

    logger.info("텔레그램 봇 초기화 완료")
    return _app
