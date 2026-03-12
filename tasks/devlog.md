# GeoLight - 개발 로그

## Phase 1: MVP 기반 구축

| # | 항목 | 상태 | 날짜 | 비고 |
|---|------|------|------|------|
| 1 | 프로젝트 초기 세팅 | 완료 | 2026-03-11 | Git, CLAUDE.md, 구조, PRD |
| 2 | config.py | 완료 | 2026-03-11 | 환경변수, 12개 이벤트, 12개 섹터 매핑, 5개 시나리오, 33개 섹터 종목 |
| 3 | infra/logging_config.py | 완료 | 2026-03-11 | RotatingFileHandler, 콘솔+파일 동시 출력 |
| 4 | storage/db.py | 완료 | 2026-03-11 | SQLite WAL, news/events/alerts/price_snapshots 테이블 |
| 5 | data/news_collector.py | 완료 | 2026-03-11 | RSS 9개 소스 + GDELT API, 중복 제거 |
| 6 | data/price_fetcher.py | 완료 | 2026-03-11 | yfinance (WTI, Brent, USD/KRW, VIX, KOSPI), 5분 캐시 |
| 7 | data/krx_data.py | 완료 | 2026-03-11 | pykrx 개별 종목 조회, 거래대금 상위, 반등 후보 |
| 8 | domain/event_classifier.py | 완료 | 2026-03-11 | 키워드 매칭 (스테밍) + Gemini LLM 보조 |
| 9 | domain/sector_mapper.py | 완료 | 2026-03-11 | 이벤트→수혜/피해 섹터→KRX 종목 |
| 10 | domain/scenario_engine.py | 완료 | 2026-03-11 | 5개 시나리오, 지표 기반 매칭, 카드 포맷 |
| 11 | domain/threshold_monitor.py | 완료 | 2026-03-11 | 임계치 감지 + 쿨다운 (메모리+DB) |
| 12 | domain/trend_detector.py | 완료 | 2026-03-11 | 거래대금 TOP + 급락 반등 후보 |
| 13 | api/telegram_bot.py | 완료 | 2026-03-11 | /now /scenario /alert /hot + 4096자 분할 |
| 14 | main.py | 완료 | 2026-03-11 | 스케줄러 + 텔레그램 봇 통합 |

## Phase 2: Action Engine + AI

| # | 항목 | 상태 | 날짜 | 비고 |
|---|------|------|------|------|
| 15 | domain/ai_assistant.py | 완료 | 2026-03-11 | Gemini REST API, /ask 명령, 일일 제한, 마크다운 변환 |
| 16 | domain/action_engine.py | 완료 | 2026-03-11 | 위험점수 계산, 5개 행동 모드, flip-flop 방지, 이력 저장 |
| 17 | domain/budget_allocator.py | 완료 | 2026-03-11 | 모드×성향→예산 비율, 금액 계산, 카드 포맷 |
| 18 | domain/user_profile.py | 완료 | 2026-03-11 | 텔레그램 사용자 설정, 한글 성향 입력, 예산 파싱 |
| 19 | config.py 확장 | 완료 | 2026-03-11 | ACTION_RISK_RULES, ACTION_MODES, BUDGET_PROFILE_MULTIPLIER, Gemini 설정 |
| 20 | storage/db.py 확장 | 완료 | 2026-03-11 | user_profiles, action_history 테이블 + CRUD |
| 21 | api/telegram_bot.py 확장 | 완료 | 2026-03-11 | /action /budget /profile /ask 추가 (총 10개 명령어) |

## Phase 3: 안정화 + 월급 배분

| # | 항목 | 상태 | 날짜 | 비고 |
|---|------|------|------|------|
| 22 | action_engine 안정화 | 완료 | 2026-03-11 | DB fallback (재시작 복원), 오늘의 가이드 캐싱, 급변 감지, threading.Lock |
| 23 | /action 카드 UX 개선 | 완료 | 2026-03-11 | 한 줄 결론 + 할 일 번호 + 참고 축약 |
| 24 | /budget 카드 UX 개선 | 완료 | 2026-03-11 | 섹터별 금액 배분, 월급 배분 섹션 |
| 25 | 월급 배분 기능 | 완료 | 2026-03-11 | monthly_income/fixed_expenses 필드, 자동 투자가능액 계산 |
| 26 | /profile 확장 | 완료 | 2026-03-11 | "소득 500만 지출 300만" 파싱, 가용자금 표시 |
| 27 | DB 마이그레이션 | 완료 | 2026-03-11 | ALTER TABLE로 monthly_income, fixed_expenses 컬럼 추가 |
| 28 | 아키텍트 리뷰 반영 | 완료 | 2026-03-11 | 이중 multiplier 방지, 파싱 edge case, 음수 가용자금 처리 |

## Phase 3.5: UX 전면 개선 + Config 중앙화 (2026-03-12 세션)

| # | 항목 | 상태 | 날짜 | 비고 |
|---|------|------|------|------|
| 29 | format_action_card 전면 재작성 | 완료 | 2026-03-12 | 시나리오 설명, 할 것/피할 것/줄일 때 구조 |
| 30 | format_budget_card 전면 재작성 | 완료 | 2026-03-12 | 한줄 요약, 섹터별 실행안, 회수 기준 |
| 31 | Config 중앙화 | 완료 | 2026-03-12 | ACTION_MODE_FLOW, ACTION_URGENT_RULES, ACTION_EVENT_BUCKETS, INDICATOR_DISPLAY_NAMES, PROFILE_NAMES |
| 32 | 텔레그램 헬퍼 함수 | 완료 | 2026-03-12 | _format_sector_line, _format_event_brief, _command_error_message, _data_unavailable_message |
| 33 | 회귀 테스트 4파일 22개 | 완료 | 2026-03-12 | test_scenario_action, test_formatters, test_telegram_bot, test_ai_assistant |

## Phase 4: 포지션 추적 + 확장

| # | 항목 | 상태 | 날짜 | 비고 |
|---|------|------|------|------|
| 34 | positions 테이블 + CRUD | 완료 | 2026-03-12 | DB UPSERT, 종목명/코드 검색, 삭제 |
| 35 | domain/portfolio.py | 완료 | 2026-03-12 | 포지션 추가/삭제, 섹터 자동매칭, 시나리오 교차분석 |
| 36 | /portfolio 텔레그램 명령 | 완료 | 2026-03-12 | 추가/수정/삭제/조회, 섹터별 비중 |
| 37 | /action 포트폴리오 연동 | 완료 | 2026-03-12 | 보유 종목 vs 시나리오 수혜/위험 분석 |
| 38 | 포트폴리오 테스트 13개 | 완료 | 2026-03-12 | test_portfolio.py |
| 39 | 조간 브리핑 자동 발송 | 예정 | - | 08:30 자동 푸시 |
| 40 | fetch_all_prices 병렬화 | 예정 | - | ThreadPoolExecutor, 1.5초→0.5초 |
| 41 | 시나리오 엔진 강화 | 예정 | - | 절대 수준 조건 + 섹터 모멘텀 |

### 통계
- 총 항목: 41
- 완료: 38
- 코드: 약 4,500줄 (Python)
- 테스트: 35개 (5파일)
