# GeoLight - 교훈 기록

## 1. pykrx batch 함수 깨짐 (2026-03-11)
- `get_market_ohlcv_by_ticker`, `get_market_cap_by_ticker` 등 batch 함수가 KRX 사이트 변경으로 컬럼 에러 발생
- **해결**: 개별 종목 `get_market_ohlcv(start, end, code)` 사용으로 대체
- **교훈**: pykrx batch API는 불안정할 수 있으므로 개별 조회 + 캐싱이 안전

## 2. 키워드 매칭 단수/복수 불일치 (2026-03-11)
- "oil price surge" 키워드가 "Oil prices surge" 텍스트와 매칭 안 됨
- **해결**: 기본 스테밍(-s, -es, -ed, -ing 제거) + 단어 집합 매칭 병합
- **교훈**: 영어 키워드 매칭은 최소한의 스테밍 필요

## 3. Gemini 모델명 변경 (2026-03-11)
- `gemini-2.0-flash` 모델이 더 이상 사용 불가 (404)
- **해결**: `gemini-2.5-flash`로 변경
- **교훈**: LLM 모델명은 자주 바뀌므로 config로 분리하면 좋음

## 4. google.generativeai 패키지 deprecated (2026-03-11)
- `google-generativeai` → `google.genai` 패키지로 전환 필요 (FutureWarning)
- 현재는 동작하지만 향후 마이그레이션 필요
