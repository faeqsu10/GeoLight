# PRD: GeoLight MVP

> 해외 뉴스/지정학 이벤트를 한국장 영향으로 번역하는 "시장 망원경" 서비스

## Problem Statement

개인투자자는 해외 뉴스(유가 급등, 중동 긴장, 미국 금리 발언 등)를 접해도 **"그래서 한국장에서 뭘 봐야 하지?"**에서 막힌다. 뉴스는 넘치는데 해석이 부족하고, 노이즈와 진짜 매매 재료를 구별하기 어렵다. 기존 Signalight는 종목 단위 시그널 분석에 강하지만, 거시/지정학 이벤트 → 섹터 영향 해석 레이어가 없다.

## Goals

1. 해외 뉴스를 수집하여 지정학/거시 이벤트로 분류하고, 한국 시장 영향 섹터·종목으로 번역
2. 시나리오별(확전/완화/쇼크 등) 수혜·피해 섹터 대응표 제공
3. 유가/환율/VIX 등 핵심 지표 임계치 돌파 시 텔레그램 실시간 알림
4. 개인투자자 관심 급증 종목(거래대금 급증, 급락 후 반등 후보) 탐색
5. 텔레그램 봇으로 즉시 사용 가능한 MVP 제공

## Non-Goals

- 종목 추천/매수·매도 시그널 (Signalight 영역)
- 자동매매/주문 실행
- 유료 뉴스 소스 크롤링 (공개 소스만 사용)
- 모바일 앱 (웹 + 텔레그램으로 충분)
- Phase 1에서 웹 대시보드 완성 (Phase 2로 분리)

## Technical Constraints

- **언어**: Python 3.11+
- **LLM**: Google Gemini API (뉴스 요약/이벤트 분류)
- **알림**: python-telegram-bot
- **DB**: SQLite (WAL 모드)
- **가격 데이터**: 무료 API (yfinance, 공개 API)
- **뉴스 소스**: RSS 피드, 공개 뉴스 API (NewsAPI 등)
- **KRX 데이터**: pykrx 또는 공개 API
- **프론트엔드 (Phase 2)**: Next.js 15, Tailwind CSS
- **배포**: 로컬 실행 우선 → 이후 서버 배포
- **LLM은 선택적 기능**: LLM 실패해도 핵심 흐름(수집 → 분류 → 매핑 → 알림) 유지

## Architecture

```
geolight/
├── config.py              # 환경변수, 섹터 매핑 사전, 임계치 설정
├── main.py                # 진입점 (스케줄러)
├── data/
│   ├── news_collector.py  # 뉴스 수집 (RSS, NewsAPI)
│   ├── price_fetcher.py   # 가격 데이터 (유가, 환율, VIX)
│   └── krx_data.py        # KRX 종목/섹터 데이터
├── domain/
│   ├── event_classifier.py    # 이벤트 분류 (규칙 기반 + LLM 보조)
│   ├── sector_mapper.py       # 이벤트 → 한국 섹터/종목 매핑
│   ├── scenario_engine.py     # 시나리오 기반 투자 지도
│   ├── threshold_monitor.py   # 임계치 모니터링
│   └── trend_detector.py      # 관심 급증 종목 탐색
├── storage/
│   └── db.py              # SQLite (이벤트 이력, 알림 이력)
├── infra/
│   └── logging_config.py  # 구조화 로깅
├── api/
│   └── telegram_bot.py    # 텔레그램 봇 (명령어 + 알림)
└── tasks/                 # 작업 추적
```

## Implementation Phases

### Phase 1: 핵심 파이프라인 (MVP)

**1-1. 인프라 기반**
- [ ] `config.py` — 환경변수 로드, 섹터 매핑 사전, 임계치 상수
- [ ] `infra/logging_config.py` — 구조화 로깅 (RotatingFileHandler)
- [ ] `storage/db.py` — SQLite 초기화, 이벤트/알림 테이블

**1-2. 데이터 수집 레이어**
- [ ] `data/news_collector.py` — RSS 피드 수집 (Reuters, Bloomberg 공개 피드 등)
- [ ] `data/price_fetcher.py` — 유가(WTI/Brent), USD/KRW, VIX 실시간 조회
- [ ] `data/krx_data.py` — KRX 섹터별 대표 종목 목록, 거래대금 조회

**1-3. 비즈니스 로직**
- [ ] `domain/event_classifier.py` — 뉴스 → 이벤트 유형 분류 (규칙 기반 키워드 매칭 + Gemini 보조)
- [ ] `domain/sector_mapper.py` — 이벤트 유형 → 수혜/피해 섹터 → KRX 종목 매핑
- [ ] `domain/threshold_monitor.py` — 가격 임계치 돌파 감지 (유가 ±7%, 환율 ±2%, VIX ±20% 등)
- [ ] `domain/scenario_engine.py` — 시나리오 정의 + 현재 상황 매칭 + 섹터별 영향 출력
- [ ] `domain/trend_detector.py` — 거래대금 급증, 급락 후 반등 후보 탐색

**1-4. 텔레그램 봇**
- [ ] `api/telegram_bot.py` — 명령어 처리 (/start, /now, /scenario, /alert, /hot)
- [ ] 뉴스 번역 결과 포맷팅 (이벤트 → 섹터 → 종목 한 줄 요약)
- [ ] 임계치 돌파 시 자동 알림 발송
- [ ] 시나리오 카드 출력

**1-5. 스케줄러 + 통합**
- [ ] `main.py` — 뉴스 수집(30분), 가격 체크(5분), 시나리오 업데이트(1시간), 헬스체크(매일 09:00)
- [ ] 전체 파이프라인 통합 테스트

### Phase 2: 웹 대시보드 + 고도화
- [ ] Next.js 웹 대시보드
- [ ] 이벤트 타임라인 시각화
- [ ] 섹터 영향 히트맵
- [ ] 시나리오 비교 뷰
- [ ] Signalight 연동

## Acceptance Criteria

> 모든 항목이 통과해야 MVP 완료

### AC1: 뉴스 수집
- [ ] RSS 피드에서 최소 1개 소스의 뉴스를 수집할 수 있다
- [ ] 중복 뉴스가 제거된다
- [ ] 수집된 뉴스가 SQLite에 저장된다

### AC2: 이벤트 분류
- [ ] 뉴스 텍스트를 입력하면 이벤트 유형(유가, 환율, 지정학, 금리 등)이 반환된다
- [ ] 규칙 기반 분류가 LLM 없이도 동작한다
- [ ] LLM 보조 분류가 실패해도 규칙 기반 결과가 반환된다

### AC3: 섹터 매핑
- [ ] 이벤트 유형을 입력하면 수혜/피해 섹터 + KRX 대표 종목이 반환된다
- [ ] 매핑 사전에 최소 8개 이벤트 유형이 정의되어 있다

### AC4: 가격 임계치 알림
- [ ] 유가, 환율, VIX 중 하나가 임계치를 돌파하면 감지된다
- [ ] 감지 시 텔레그램으로 알림이 발송된다
- [ ] 같은 이벤트에 대해 중복 알림이 방지된다 (쿨다운)

### AC5: 시나리오 엔진
- [ ] 최소 3개 시나리오(확전, 완화, 쇼크)가 정의되어 있다
- [ ] 각 시나리오에 수혜/피해 섹터가 매핑되어 있다
- [ ] 현재 지표 기반으로 가장 가까운 시나리오가 추천된다

### AC6: 관심 급증 종목
- [ ] 거래대금 기준 상위 종목을 조회할 수 있다
- [ ] 급락 후 반등 후보를 필터링할 수 있다

### AC7: 텔레그램 봇
- [ ] `/now` — 현재 주요 이벤트 + 영향 섹터 요약 반환
- [ ] `/scenario` — 현재 시나리오 카드 반환
- [ ] `/alert` — 알림 설정 상태 확인
- [ ] `/hot` — 관심 급증 종목 목록 반환
- [ ] 메시지가 4096자를 초과하지 않는다

### AC8: 스케줄러
- [ ] main.py 실행 시 즉시 1회 실행 후 스케줄 등록
- [ ] 30분마다 뉴스 수집, 5분마다 가격 체크가 동작한다
- [ ] 프로세스가 에러로 중단되지 않는다 (예외 격리)

### AC9: 인프라
- [ ] 모든 모듈이 import 에러 없이 로드된다
- [ ] 로그가 파일과 콘솔에 동시 출력된다
- [ ] .env 미설정 시 명확한 경고 메시지 후 graceful degradation

## Key Metrics (성공 지표)

- 뉴스 수집 → 섹터 매핑까지 **30초 이내** 완료
- 가격 임계치 돌파 → 텔레그램 알림까지 **1분 이내**
- 하루 LLM API 호출 **100회 이내** (비용 관리)
- 텔레그램 봇 응답 **5초 이내**
