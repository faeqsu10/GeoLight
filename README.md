# GeoLight — 시장 망원경

해외 뉴스와 지정학 이벤트를 한국장 영향으로 번역하는 개인 투자 보조 시스템.

## 핵심 기능

- **이벤트 감지**: RSS 9개 소스 + GDELT API에서 해외 뉴스 수집 → 12개 이벤트 유형 분류
- **섹터 매핑**: 이벤트 → 수혜/피해 한국 섹터 → KRX 종목 연결 (33개 종목)
- **시나리오 투자 지도**: 5개 시나리오(확전, 완화, 시장쇼크, 긴축, 금리완화) + 절대 수준 조건
- **행동 엔진**: 위험점수 기반 5개 행동 모드 + flip-flop 방지(1단계 전이 + 6시간 쿨다운)
- **예산 배분**: 행동 모드 × 투자 성향 → 섹터별 금액 배분 + 월급 배분(투자/저축/비상금)
- **포트폴리오**: 보유 종목 관리 + 시나리오 교차 분석(수혜/위험 종목 자동 식별)
- **조간 브리핑**: 매일 08:30 핵심 지표 + 행동 카드 자동 텔레그램 발송
- **임계치 알림**: 유가/환율/VIX/KOSPI 급변 시 텔레그램 자동 알림
- **관심 종목**: 거래대금 급증 + 급락 반등 후보 탐색
- **AI 분석**: Gemini REST API 기반 시장 분석 Q&A

## 텔레그램 명령어

| 명령어 | 기능 |
|--------|------|
| `/now` | 현재 주요 이벤트 + 영향 섹터 |
| `/scenario` | 시나리오 투자 지도 |
| `/action` | 오늘의 행동 가이드 (포트폴리오 연동) |
| `/budget` | 예산/월급 집행 가이드 (섹터별 배분) |
| `/portfolio` | 보유 종목 관리 (추가/수정/삭제) |
| `/profile` | 투자 설정 (성향/예산/소득/지출) |
| `/alert` | 알림 설정 상태 |
| `/hot` | 관심 급증 종목 |
| `/ask [질문]` | AI 시장 분석 |
| `/help` | 전체 명령 안내 |

## 기술 스택

- **Python 3.12** — 백엔드 전체
- **SQLite (WAL)** — 8개 테이블 (뉴스, 이벤트, 알림, 가격, 프로필, 행동 이력, 포지션)
- **python-telegram-bot** — 텔레그램 봇 인터페이스
- **yfinance** — 실시간 가격 (WTI, Brent, USD/KRW, VIX, KOSPI) — 병렬 조회
- **pykrx** — KRX 종목 데이터
- **Gemini REST API** — 이벤트 분류 보조 + AI Q&A (직접 HTTP 호출, SDK 의존성 없음)
- **schedule** — 주기적 뉴스 수집/가격 감시/조간 브리핑
- **pytest** — 35개 회귀 테스트

## 프로젝트 구조

```
geolight/
├── main.py                  # 진입점 (스케줄러 + 봇)
├── config.py                # 전체 설정 (지표, 시나리오, 행동 규칙)
├── data/
│   ├── news_collector.py    # RSS + GDELT 뉴스 수집
│   ├── price_fetcher.py     # yfinance 가격 병렬 조회
│   └── krx_data.py          # KRX 종목 데이터
├── domain/
│   ├── event_classifier.py  # 뉴스 → 이벤트 분류
│   ├── sector_mapper.py     # 이벤트 → 섹터 → 종목
│   ├── scenario_engine.py   # 시나리오 매칭
│   ├── action_engine.py     # 행동 모드 판단
│   ├── budget_allocator.py  # 예산/월급 배분
│   ├── portfolio.py         # 보유 종목 관리 + 시나리오 연동
│   ├── user_profile.py      # 사용자 설정
│   ├── threshold_monitor.py # 임계치 감지
│   ├── trend_detector.py    # 관심 종목 탐색
│   └── ai_assistant.py      # Gemini AI Q&A
├── storage/
│   └── db.py                # SQLite 영속성 (8개 테이블)
├── api/
│   └── telegram_bot.py      # 텔레그램 봇 (11개 명령)
├── infra/
│   └── logging_config.py    # 로깅 설정
└── tests/                   # 35개 회귀 테스트
    ├── test_scenario_action.py
    ├── test_formatters.py
    ├── test_telegram_bot.py
    ├── test_ai_assistant.py
    └── test_portfolio.py
```

## 설치 및 실행

```bash
# 가상환경 생성
python3 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY 입력

# 실행
python3 main.py
```

## 환경변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `TELEGRAM_BOT_TOKEN` | O | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | O | 알림 수신 채팅 ID |
| `GEMINI_API_KEY` | - | Google Gemini API 키 (없으면 AI 기능 비활성) |
| `DB_PATH` | - | SQLite DB 경로 (기본: `geolight.db`) |
| `GEMINI_MODEL` | - | Gemini 모델 (기본: `gemini-2.5-flash`) |
| `GEMINI_DAILY_LIMIT` | - | 일일 AI 질문 허용 횟수 (기본: `10`) |

> `.env` 파일은 `.gitignore`에 등록되어 있으며 저장소에 포함되지 않습니다.

## 데이터 흐름

```
해외 뉴스 (RSS/GDELT) → 이벤트 분류 → 섹터 매핑 → DB 저장
                                          │
가격 수집 (yfinance 병렬) → 위험점수 계산 → 행동 모드 판단
                                │               │
                          임계치 감지      예산/월급 배분
                                │               │
                                └──── 텔레그램 봇 ────┘
                                         │
                          포트폴리오 ← 시나리오 교차 분석
```

## 스케줄

| 주기 | 작업 |
|------|------|
| 30분 | 뉴스 수집 + 이벤트 분류 |
| 5분 | 가격 조회 + 임계치 알림 |
| 60분 | 시나리오 재평가 |
| 매일 08:30 | 조간 브리핑 자동 발송 |
| 매일 09:00 | 헬스체크 |

## 테스트

```bash
# 전체 테스트 실행 (35개)
python3 -m pytest tests/ -v

# 특정 모듈만
python3 -m pytest tests/test_portfolio.py -v
```

## 보안 고려사항

- API 토큰/키는 `.env`로만 관리, 코드에 하드코딩 금지
- `.env`, `.db`, `.claude/` 등 민감 파일은 `.gitignore`로 추적 제외
- 텔레그램 메시지 4096자 분할 전송으로 데이터 유출 방지
- LLM API 실패 시 핵심 기능(가격 조회, 섹터 매핑) 정상 동작 유지
- 사용자 입력(종목명, 금액)은 파싱/검증 후 처리
- SQL 쿼리 전부 파라미터 바인딩 사용 (injection 방지)
