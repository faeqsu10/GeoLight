"""GeoLight 텔레그램 봇 — 명령어 처리 + 알림 발송."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import (
    INDICATOR_DISPLAY_NAMES,
    TELEGRAM_ALLOWED_USERS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_MAX_LENGTH,
)
from data.news_collector import collect_all_news
from data.price_fetcher import build_indicators, fetch_all_prices
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
from domain.portfolio import (
    add_position,
    remove_position,
    format_portfolio,
    analyze_portfolio_vs_scenario,
    format_portfolio_action_advice,
    get_user_positions,
)
from domain.user_profile import get_profile, update_profile, format_profile
from storage.db import get_recent_events

logger = logging.getLogger("geolight.api.telegram")

_app: Optional[Application] = None
_ai: Optional[AIAssistant] = None


# ── 인증 ─────────────────────────────────────────────────

def _authorized(func):
    """텔레그램 봇 접근 제어 데코레이터."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if TELEGRAM_ALLOWED_USERS and update.effective_user.id not in TELEGRAM_ALLOWED_USERS:
            logger.warning("미허가 접근: user_id=%d", update.effective_user.id)
            await update.message.reply_text("접근 권한이 없습니다.")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ── 메시지 분할 전송 ──────────────────────────────────────

def _split_text(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """긴 텍스트를 줄 단위로 분할."""
    if len(text) <= max_length:
        return [text]
    chunks = []
    chunk = ""
    for line in text.split("\n"):
        if len(chunk) + len(line) + 1 > max_length:
            if chunk:
                chunks.append(chunk)
            chunk = line
        else:
            chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        chunks.append(chunk)
    return chunks


async def _send_message(chat_id: str, text: str, context: ContextTypes.DEFAULT_TYPE):
    """4096자 제한 대응 분할 전송."""
    for chunk in _split_text(text):
        await context.bot.send_message(chat_id=chat_id, text=chunk)


def _format_sector_line(entries: list[dict]) -> str:
    sectors = [entry.get("sector", "") for entry in entries if entry.get("sector")]
    return ", ".join(sectors[:3]) if sectors else "없음"


def _format_event_brief(mapping: dict, title: str = "") -> list[str]:
    lines = [
        f"[{mapping['event_type']}] 수혜: {_format_sector_line(mapping.get('beneficiary', []))} | "
        f"피해: {_format_sector_line(mapping.get('damaged', []))}"
    ]
    if title:
        lines.append(f"  뉴스: {title[:70]}")
    return lines


def _command_error_message(command: str, detail: str) -> str:
    return (
        f"{command} 결과를 지금 만들지 못했습니다.\n"
        f"{detail}\n"
        "잠시 뒤 다시 시도해 주세요."
    )


def _data_unavailable_message(subject: str, next_step: str) -> str:
    return (
        f"지금은 {subject}를 불러오지 못했습니다.\n"
        f"{next_step}"
    )


async def send_alert(text: str):
    """외부에서 호출하는 알림 발송 (스케줄러용)."""
    if not _app or not TELEGRAM_CHAT_ID:
        logger.warning("텔레그램 앱 미초기화 또는 CHAT_ID 미설정")
        return

    try:
        for chunk in _split_text(text):
            await _app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=chunk)
    except Exception as e:
        logger.warning("텔레그램 알림 발송 실패: %s", e)


# ── 명령어 핸들러 ─────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """봇 시작 메시지."""
    text = (
        "GeoLight — 시장 망원경\n"
        "해외 뉴스와 시장 지표를 한국 투자 관점으로 요약합니다.\n\n"
        "바로 써볼 명령:\n"
        "/now  현재 이벤트와 핵심 지표\n"
        "/action  오늘 매수/관망 판단\n"
        "/budget  이번 달 예산 실행안\n"
        "/profile  내 성향/예산 설정\n"
        "/help  전체 명령 안내"
    )
    await update.message.reply_text(text)


@_authorized
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

            lines = ["GeoLight — 현재 이벤트 요약", ""]

            if unique_events:
                top_event = unique_events[0]["event_type"]
                lines.append(f"한줄 해석: 지금은 `{top_event}` 흐름을 가장 먼저 볼 구간입니다.")
                lines.append("")

            for evt in unique_events[:5]:
                mapping = map_event_to_sectors(evt["event_type"])
                if mapping:
                    lines.extend(_format_event_brief(mapping, evt.get("title", "")))
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
                await update.message.reply_text(
                    _data_unavailable_message(
                        "뉴스 데이터",
                        "/scenario 또는 /alert 로 가격 지표부터 먼저 확인할 수 있습니다.",
                    )
                )
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
                await update.message.reply_text(
                    "지금은 뚜렷한 이벤트가 감지되지 않았습니다.\n"
                    "대신 /scenario 나 /action 으로 가격 기반 판단을 먼저 확인해 보세요."
                )
                return

            seen_types = set()
            unique_events = []
            for evt in all_events:
                if evt["event_type"] not in seen_types:
                    seen_types.add(evt["event_type"])
                    unique_events.append(evt)

            mappings = translate_news_to_sectors(unique_events)
            lines = ["GeoLight — 현재 이벤트 요약", ""]
            for m in mappings[:5]:
                lines.extend(_format_event_brief(m))
                lines.append("")

        # 가격 현황 추가
        prices = fetch_all_prices()
        if prices:
            if len(lines) > 2:
                lines.append("지금 먼저 볼 지표")
                lines.append("-" * 25)
            lines.append("주요 지표")
            lines.append("-" * 25)
            for ind, p in prices.items():
                name = INDICATOR_DISPLAY_NAMES.get(ind, ind)
                lines.append(f"  {name}: {p['value']:,.2f} ({p['change_pct']:+.2f}%)")

        text = "\n".join(lines)
        await _send_message(update.effective_chat.id, text, context)

    except Exception as e:
        logger.error("/now 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(
            _command_error_message(
                "/now",
                "뉴스 또는 가격 데이터를 가져오는 중 일시적 문제가 발생했습니다.",
            )
        )


@_authorized
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
        await update.message.reply_text(
            _command_error_message(
                "/scenario",
                "가격 지표를 기반으로 시나리오를 계산하는 중 문제가 발생했습니다.",
            )
        )


@_authorized
async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """알림 상태 확인."""
    from config import THRESHOLDS

    lines = [
        "GeoLight — 알림 설정 상태",
        "한줄 해석: 아래 기준을 넘기면 자동 알림이 발송됩니다.",
        "",
    ]

    for ind, cfg in THRESHOLDS.items():
        name = INDICATOR_DISPLAY_NAMES.get(ind, ind)
        lines.append(
            f"- {name}: 전일 대비 ±{cfg['pct']}% 이상, 이후 {cfg['cooldown_min']}분 쿨다운"
        )

    lines.append("")
    lines.append("예시")
    lines.append("-" * 25)
    lines.append("USD/KRW가 하루에 +2% 이상 움직이면 환율 급변 알림이 갑니다.")
    lines.append("VIX가 +20% 이상 급등하면 변동성 경고 알림이 갑니다.")

    await update.message.reply_text("\n".join(lines))


@_authorized
async def cmd_hot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """관심 급증 종목."""
    await update.message.reply_text("종목 데이터 조회 중...")

    try:
        data = detect_hot_stocks(top_n=15)
        text = f"GeoLight — 관심 급증 종목\n{'=' * 30}\n\n{format_hot_stocks(data)}"
        await _send_message(update.effective_chat.id, text, context)
    except Exception as e:
        logger.error("/hot 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(
            _command_error_message(
                "/hot",
                "종목 데이터를 조회하는 중 문제가 발생했습니다.",
            )
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """도움말."""
    text = (
        "GeoLight 명령어 안내\n\n"
        "지금 시장 보기\n"
        "- /now  현재 이벤트와 핵심 지표 요약\n"
        "- /scenario  지금 우세한 시나리오와 볼/피할 섹터\n"
        "- /alert  자동 알림 기준 확인\n"
        "- /hot  수급 몰림 종목과 낙폭 큰 종목 보기\n\n"
        "오늘 행동 정하기\n"
        "- /action  오늘 매수/관망 판단\n"
        "- /budget  이번 달 예산 실행안\n\n"
        "내 포트폴리오\n"
        "- /portfolio  보유 종목 목록\n"
        "- /portfolio 삼성전자 70000 10  종목 추가\n"
        "- /portfolio 삭제 삼성전자  종목 삭제\n\n"
        "내 설정\n"
        "- /profile  현재 설정 보기\n"
        "- /profile 공격 200만\n"
        "- /profile 소득 500만 지출 300만\n\n"
        "질문하기\n"
        "- /ask 중동 긴장이 한국 반도체에 미치는 영향은?\n"
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


@_authorized
async def cmd_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """오늘의 행동 가이드."""
    await update.message.reply_text("행동 모드 분석 중...")

    try:
        prices = fetch_all_prices()
        if not prices:
            await update.message.reply_text(
                _data_unavailable_message(
                    "가격 지표",
                    "/now 또는 /alert 는 먼저 확인할 수 있을 수 있습니다.",
                )
            )
            return

        indicators = build_indicators(prices)
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

        # 포트폴리오 보유 시 맞춤 조언 추가
        positions = get_user_positions(user_id)
        if positions and result.get("focus_sectors"):
            beneficiary = scenario.get("beneficiary_sectors", []) if scenario else []
            damaged = scenario.get("damaged_sectors", []) if scenario else []
            if beneficiary or damaged:
                analysis = analyze_portfolio_vs_scenario(
                    user_id, beneficiary, damaged,
                )
                advice = format_portfolio_action_advice(analysis, result["mode_key"])
                if advice.strip():
                    text += "\n\n" + advice

        await _send_message(update.effective_chat.id, text, context)

    except Exception as e:
        logger.error("/action 처리 실패: %s", e, exc_info=True)
        await update.message.reply_text(
            _command_error_message(
                "/action",
                "행동 모드를 계산하는 중 문제가 발생했습니다.",
            )
        )


@_authorized
async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """예산 집행 가이드."""
    try:
        prices = fetch_all_prices()
        if not prices:
            await update.message.reply_text(
                _data_unavailable_message(
                    "가격 지표",
                    "/profile 설정은 유지되며, 잠시 뒤 /budget 을 다시 시도해 주세요.",
                )
            )
            return

        indicators = build_indicators(prices)
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
        await update.message.reply_text(
            _command_error_message(
                "/budget",
                "예산 실행안을 계산하는 중 문제가 발생했습니다.",
            )
        )


@_authorized
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
        await update.message.reply_text(
            _command_error_message(
                "/profile",
                "설정을 저장하는 중 문제가 발생했습니다.",
            )
        )


@_authorized
async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """보유 종목 관리."""
    user_id = update.effective_user.id
    args = context.args or []

    if not args:
        # 인자 없으면 포트폴리오 표시
        text = format_portfolio(user_id)
        await _send_message(update.effective_chat.id, text, context)
        return

    # /portfolio 삭제 종목명
    if args[0] in ("삭제", "제거", "del", "remove"):
        if len(args) < 2:
            await update.message.reply_text(
                "삭제할 종목명을 입력해주세요.\n예: /portfolio 삭제 삼성전자"
            )
            return
        stock_name = " ".join(args[1:])
        if remove_position(user_id, stock_name):
            await update.message.reply_text(f"{stock_name} 포지션을 삭제했습니다.")
        else:
            await update.message.reply_text(
                f"'{stock_name}'에 해당하는 보유 종목을 찾지 못했습니다.\n"
                "/portfolio 로 보유 목록을 확인해주세요."
            )
        return

    # /portfolio 종목명 평단가 수량 [메모]
    if len(args) < 3:
        await update.message.reply_text(
            "종목 추가 형식: /portfolio 종목명 평단가 수량\n\n"
            "예시\n"
            "-" * 25 + "\n"
            "/portfolio 삼성전자 70000 10\n"
            "/portfolio 현대차 200000 5\n"
            "/portfolio 삭제 삼성전자"
        )
        return

    stock_name = args[0]

    # 평단가 파싱
    avg_price = _parse_amount(args[1])
    if avg_price is None:
        # _parse_amount는 10만 미만을 거부하므로 직접 파싱
        try:
            avg_price = int(args[1])
            if avg_price <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                f"평단가 '{args[1]}'를 인식하지 못했습니다.\n숫자로 입력해주세요. 예: 70000"
            )
            return

    # 수량 파싱
    try:
        quantity = int(args[2])
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            f"수량 '{args[2]}'를 인식하지 못했습니다.\n양의 정수로 입력해주세요. 예: 10"
        )
        return

    memo = " ".join(args[3:]) if len(args) > 3 else ""

    try:
        result = add_position(user_id, stock_name, avg_price, quantity, memo)
        sector_info = f" [{result['sector']}]" if result["sector"] else ""
        text = (
            f"{result['stock_name']}{sector_info} 포지션 저장 완료\n"
            f"  {quantity}주 × {avg_price:,}원 = {result['total']:,}원\n\n"
            "/portfolio 로 전체 보유 목록을 확인할 수 있습니다."
        )
        await update.message.reply_text(text)
    except Exception as e:
        logger.error("/portfolio 추가 실패: %s", e, exc_info=True)
        await update.message.reply_text(
            _command_error_message("/portfolio", "종목을 저장하는 중 문제가 발생했습니다.")
        )


@_authorized
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
        await update.message.reply_text(
            _command_error_message(
                "/ask",
                "AI 응답을 만드는 중 문제가 발생했습니다.",
            )
        )


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
    _app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    _app.add_handler(CommandHandler("ask", cmd_ask))
    _app.add_handler(CommandHandler("help", cmd_help))

    logger.info("텔레그램 봇 초기화 완료")
    return _app
