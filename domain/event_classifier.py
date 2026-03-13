"""이벤트 분류 — 규칙 기반 키워드 매칭 + Gemini LLM 보조."""

import json
import logging
from typing import Optional

from config import EVENT_KEYWORDS, EVENT_TYPES, GEMINI_API_KEY

logger = logging.getLogger("geolight.domain.classifier")


def classify_by_keywords(text: str) -> list[dict]:
    """규칙 기반 키워드 매칭으로 이벤트 유형 분류.

    구문(phrase) 매칭 + 개별 단어(word) 매칭을 병합.
    Returns:
        [{"event_type": str, "score": float, "matched_keywords": list[str]}, ...]
    """
    text_lower = text.lower()
    # 단어 집합 (복수형 → 단수형 기본 스테밍)
    raw_words = set(text_lower.split())
    words = set()
    for w in raw_words:
        words.add(w)
        # 기본 스테밍: -s, -es, -ed, -ing 제거
        if w.endswith("es") and len(w) > 3:
            words.add(w[:-2])
        if w.endswith("s") and not w.endswith("ss") and len(w) > 2:
            words.add(w[:-1])
        if w.endswith("ed") and len(w) > 3:
            words.add(w[:-2])
        if w.endswith("ing") and len(w) > 4:
            words.add(w[:-3])

    results = []

    for event_type, keywords in EVENT_KEYWORDS.items():
        matched = []
        for kw in keywords:
            kw_lower = kw.lower()
            # 1) 구문 매칭 (원래 방식)
            if kw_lower in text_lower:
                matched.append(kw)
                continue
            # 2) 키워드의 모든 단어가 텍스트에 포함되면 매칭 (스테밍 적용)
            kw_words = set(kw_lower.split())
            if len(kw_words) > 1 and kw_words.issubset(words):
                matched.append(kw)

        if matched:
            score = min(1.0, len(matched) / 3.0)
            results.append({
                "event_type": event_type,
                "score": round(score, 2),
                "matched_keywords": matched,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def classify_by_llm(text: str) -> Optional[list[dict]]:
    """Gemini REST API로 이벤트 분류 (선택적 기능)."""
    if not GEMINI_API_KEY:
        return None

    try:
        import requests
        from config import GEMINI_MODEL

        prompt = f"""다음 뉴스 텍스트를 분석하여 이벤트 유형을 분류하세요.

가능한 이벤트 유형: {', '.join(EVENT_TYPES)}

뉴스 텍스트:
{text[:1000]}

반드시 JSON 형식으로만 응답하세요:
[{{"event_type": "이벤트유형", "confidence": 0.0~1.0, "reason": "분류 이유"}}]

최대 3개까지만 반환하세요. 해당 없으면 빈 배열 []을 반환하세요."""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        resp = requests.post(
            url,
            headers={"x-goog-api-key": GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.3},
            },
            timeout=15,
        )

        if resp.status_code != 200:
            logger.warning("Gemini API 오류: %d", resp.status_code)
            return None

        candidates = resp.json().get("candidates", [])
        if not candidates:
            return None

        raw = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not raw:
            return None

        raw = raw.strip()

        # 마크다운 코드블록 제거
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]

        # JSON 추출
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            results = []
            for item in data[:3]:
                et = item.get("event_type", "")
                if et in EVENT_TYPES:
                    results.append({
                        "event_type": et,
                        "score": max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                        "reason": item.get("reason", ""),
                    })
            return results if results else None

    except Exception as e:
        logger.warning("LLM 분류 실패: %s", e)

    return None


def classify_news(title: str, summary: str = "") -> list[dict]:
    """뉴스를 분류하여 이벤트 유형 리스트 반환.

    규칙 기반을 우선 사용하고, LLM은 보조로 활용.
    LLM 실패 시 규칙 기반 결과만 반환.
    """
    text = f"{title} {summary}"

    # 1) 규칙 기반 분류
    rule_results = classify_by_keywords(text)

    # 2) LLM 보조 분류 (규칙 기반 결과가 없거나 점수 낮을 때)
    if not rule_results or (rule_results and rule_results[0]["score"] < 0.5):
        llm_results = classify_by_llm(text)
        if llm_results:
            existing_types = {r["event_type"] for r in rule_results}
            for lr in llm_results:
                if lr["event_type"] not in existing_types:
                    rule_results.append(lr)

    return rule_results
