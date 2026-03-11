"""GeoLight AI 어시스턴트 — Gemini 기반 /ask 처리."""

import re
import html as html_mod
import logging
from datetime import date
from typing import Optional

import requests

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MAX_TOKENS, GEMINI_DAILY_LIMIT

logger = logging.getLogger("geolight.domain.ai")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

SYSTEM_PROMPT = (
    "당신은 지정학·거시경제 전문 투자 어시스턴트입니다. "
    "GeoLight 서비스의 사용자에게 해외 뉴스/이벤트가 한국 주식시장에 미치는 영향을 "
    "섹터·종목 단위로 간결하고 실용적으로 분석해줍니다. "
    "답변은 텔레그램 메시지에 적합하게 짧고 명확하게 작성합니다. "
    "투자 조언이 아닌 정보 제공임을 유의합니다. "
    "가능하면 수혜/피해 섹터와 대표 종목을 함께 언급합니다."
)


def markdown_to_telegram_html(text: str) -> str:
    """마크다운 텍스트를 텔레그램 HTML로 변환."""
    text = html_mod.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


class AIAssistant:
    def __init__(self):
        self._api_key = GEMINI_API_KEY
        self._model = GEMINI_MODEL
        self._client = requests.Session()
        self._daily_limit = GEMINI_DAILY_LIMIT
        self._usage_date: Optional[date] = None
        self._usage_count = 0

    @property
    def remaining_today(self) -> int:
        if self._usage_date != date.today():
            return self._daily_limit
        return max(0, self._daily_limit - self._usage_count)

    def ask(self, question: str, context: str = "") -> str:
        """질문에 답변. 일일 제한 초과 시 안내 메시지 반환."""
        if not self._api_key:
            return "GEMINI_API_KEY가 설정되지 않았습니다."

        today = date.today()
        if self._usage_date != today:
            self._usage_date = today
            self._usage_count = 0

        if self._usage_count >= self._daily_limit:
            return f"일일 사용 제한({self._daily_limit}회)에 도달했습니다. 내일 다시 이용해주세요."

        user_content = question
        if context:
            user_content = f"[현재 시장 상황]\n{context}\n\n[질문]\n{question}"

        try:
            resp = self._client.post(
                f"{GEMINI_API_BASE}/{self._model}:generateContent",
                params={"key": self._api_key},
                json={
                    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": [{"parts": [{"text": user_content}]}],
                    "generationConfig": {
                        "maxOutputTokens": GEMINI_MAX_TOKENS,
                        "temperature": 0.7,
                    },
                },
                timeout=30,
            )

            if resp.status_code != 200:
                logger.warning("Gemini API 오류: %d %s", resp.status_code, resp.text[:200])
                return f"AI 응답 오류 ({resp.status_code}). 잠시 후 다시 시도해주세요."

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return "AI가 응답을 생성하지 못했습니다."

            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not text:
                return "AI 응답이 비어있습니다."

            self._usage_count += 1
            logger.info("/ask 응답 완료 (사용: %d/%d)", self._usage_count, self._daily_limit)
            return text

        except requests.Timeout:
            return "AI 응답 시간 초과. 잠시 후 다시 시도해주세요."
        except Exception as e:
            logger.error("/ask 처리 실패: %s", e, exc_info=True)
            return f"AI 처리 오류: {e}"


def build_market_context() -> str:
    """AI 질문에 첨부할 현재 시장 컨텍스트."""
    lines = []

    # 가격 데이터
    try:
        from data.price_fetcher import fetch_all_prices
        prices = fetch_all_prices()
        if prices:
            names = {
                "oil_wti": "WTI 유가",
                "oil_brent": "브렌트유",
                "usd_krw": "USD/KRW",
                "vix": "VIX",
                "kospi": "KOSPI",
            }
            for ind, p in prices.items():
                name = names.get(ind, ind)
                lines.append(f"{name}: {p['value']:,.2f} ({p['change_pct']:+.2f}%)")
    except Exception:
        pass

    # 최근 이벤트
    try:
        from storage.db import get_recent_events
        events = get_recent_events(limit=10)
        if events:
            seen = set()
            lines.append("")
            lines.append("최근 감지된 이벤트:")
            for evt in events:
                if evt["event_type"] not in seen:
                    seen.add(evt["event_type"])
                    title = evt.get("title", "")[:60]
                    lines.append(f"  - [{evt['event_type']}] {title}")
    except Exception:
        pass

    # 시나리오
    try:
        from domain.scenario_engine import find_best_scenario
        from data.price_fetcher import fetch_all_prices
        prices = fetch_all_prices()
        indicators = {}
        for ind, p in prices.items():
            indicators[f"{ind}_change_pct"] = p["change_pct"]
            indicators[ind] = p["value"]
        best = find_best_scenario(indicators)
        if best and best["score"] > 0:
            lines.append(f"\n현재 시나리오: {best['name']} ({best['score']*100:.0f}%)")
    except Exception:
        pass

    return "\n".join(lines)
