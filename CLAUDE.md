# GeoLight - Claude Code 프로젝트 가이드

> 해외 뉴스/지정학 이벤트를 한국장 영향으로 번역하는 "시장 망원경" 서비스.
> Signalight("종목 현미경")의 인접 서비스.

## 프로젝트 개요
해외 헤드라인과 지정학/거시 이벤트를 수집·분류하여, 한국 시장에 미치는 영향을 섹터·종목 단위로 번역해주는 서비스.
- **백엔드**: Python 기반, 뉴스 수집 → 이벤트 분류 → 섹터 매핑 → 알림 발송
- **프론트엔드**: Next.js 기반, 이벤트 대시보드 + 섹터 영향 시각화
- **데이터**: 공개 뉴스 API, 가격 API(유가/환율/VIX), KRX 종목 데이터, SQLite

## 핵심 기능
1. **해외 뉴스 → 한국장 번역기**: 해외 뉴스 수집 → 이벤트 분류 → 국내 영향 섹터 매핑 → KRX 종목 연결
2. **시나리오 기반 투자 지도**: 확전/완화/쇼크 등 시나리오별 수혜/피해 섹터 대응표
3. **임계치 기반 알림봇**: 유가/환율/VIX 등 급변 시 텔레그램 알림
4. **개인투자자 관심 급증 종목 탐색기**: 급락 후 반등 후보, 거래대금 급증, 관심 키워드 급등

## 아키텍처

```
geolight/
├── CLAUDE.md              # 프로젝트 가이드 (이 파일)
├── config.py              # 설정 (환경변수, 파라미터, 섹터 매핑 사전)
├── main.py                # 진입점 (스케줄러)
├── data/                  # 외부 데이터 수집 레이어
│   ├── news_collector.py  # 뉴스 수집 (Reuters, 공개 소스)
│   ├── price_fetcher.py   # 가격 데이터 (유가, 환율, VIX)
│   └── krx_data.py        # KRX 종목/섹터 데이터
├── domain/                # 비즈니스 로직 레이어
│   ├── event_classifier.py    # 이벤트 분류 (지정학, 유가, 환율, 금리)
│   ├── sector_mapper.py       # 이벤트 → 한국 섹터 매핑
│   ├── scenario_engine.py     # 시나리오 기반 투자 지도
│   ├── trend_detector.py      # 관심 급증 종목 탐색
│   └── portfolio.py           # 보유 종목(포지션) 관리 + 시나리오 연동
├── storage/               # 영속성 레이어
│   └── db.py              # SQLite (이벤트 이력, 매핑 사전)
├── infra/                 # 인프라
│   └── logging_config.py  # 로깅 설정
├── api/                   # 외부 인터페이스
│   └── telegram_bot.py    # 텔레그램 알림 봇
│
├── web/                   # 프론트엔드 (Phase 2)
│   ├── app/               # Next.js 라우트/페이지
│   ├── components/        # UI 컴포넌트
│   └── lib/               # 유틸리티/비즈니스 로직
│
├── tasks/                 # 작업 추적 문서
│   ├── todo.md            # 현재 작업 체크리스트
│   ├── devlog.md          # 전체 개발 항목 추적
│   ├── lessons.md         # 교훈 기록
│   └── improvements.md    # 개선사항 추적 (P0~P3)
│
├── docs/                  # 문서
├── logs/                  # 로그 파일 (gitignore)
├── .env.example           # 환경변수 목록
└── .gitignore
```

## 기술 스택

### 백엔드
- Python 3.11+
- `requests` — HTTP 클라이언트 (뉴스/가격 API)
- `schedule` — 스케줄링
- `python-telegram-bot` — 텔레그램 봇
- Gemini REST API — 뉴스 분류/AI 질답 (직접 HTTP 호출)
- `sqlite3` — 내장 DB

### 프론트엔드 (Phase 2)
- Next.js 15 (App Router)
- Tailwind CSS
- SWR (데이터 페칭)
- Recharts (차트)

## 핵심 규칙 (Gotchas)

> 실제 실수가 발생했던 항목만 기록. 개발 진행하면서 추가.

- 뉴스 크롤링 시 **User-Agent 헤더 필수** — 없으면 403
- 텔레그램 메시지 **4096자 제한** — 긴 메시지는 분할 전송
- KRX 데이터 인코딩 **euc-kr** 주의
- LLM API 호출은 **선택적 기능** — 실패해도 핵심 흐름 유지

## 섹터 매핑 사전 (핵심 도메인 지식)

> 이벤트 → 한국장 영향 섹터의 기본 매핑. domain/sector_mapper.py에 구현.

| 이벤트 | 수혜 섹터 | 피해 섹터 |
|--------|-----------|-----------|
| 유가 급등 | 정유, 해운, 탱커 | 항공, 화학 |
| 유가 급락 | 항공, 소비, 여행 | 정유, 에너지 |
| 환율(USD/KRW) 급등 | 수출주(반도체, 자동차) | 수입주, 내수 |
| 중동 긴장 확대 | 방산, LNG, 에너지 | 항공, 여행, 소비 |
| 중동 긴장 완화 | 항공, 여행, 소비 | 방산 |
| VIX 급등 | 인버스 ETF | 성장주, 소형주 |
| 미국 금리 인상 시사 | 은행, 보험 | 성장주, 부동산 |
| 미국 금리 인하 시사 | 성장주, 부동산, 리츠 | 은행 |

## 커밋 보안 규칙

**커밋 금지 파일** (`.gitignore`에 등록됨):
- `.env`, `.env.*` — API 토큰, 시크릿
- `.claude/` — Claude Code 세션/에이전트 데이터
- `.omc/state/`, `.omc/project-memory.json` — 플러그인 상태 파일
- `*.png`, `*.jpg` — 스크린샷/이미지 파일
- `node_modules/`, `__pycache__/`, `.next/`, `dist/` — 빌드 산출물
- `*.db`, `*.sqlite` — 로컬 데이터베이스

**커밋 전 체크**: `git status`로 민감 파일 미포함 확인 필수

## 자동 수행 규칙 (유저가 말하지 않아도 항상)

1. **작업 완료 시 커밋** — 의미 있는 단위로 커밋, 보안 파일 제외 확인
2. **문서 업데이트** — 구조/기능 변경 시 `tasks/todo.md`, `lessons.md`, `improvements.md`, `devlog.md` 갱신
3. **CLAUDE.md 동기화** — 프로젝트 구조 변경 시 아키텍처 섹션 업데이트
4. **테스트 검증** — 코드 작성 후 import/실행 테스트로 동작 확인
5. **교훈 기록** — 실수나 새로운 발견은 `tasks/lessons.md`에 기록

## Workflow Orchestration

### 1. Plan First
- 3단계 이상이거나 구조적 결정이 필요한 작업은 plan mode 진입
- 문제가 생기면 즉시 멈추고 재계획 — 밀어붙이지 않는다
- 검증 단계도 계획에 포함

### 2. Subagent 전략
- 메인 컨텍스트를 깔끔하게 유지하기 위해 subagent 적극 활용
- 리서치, 탐색, 병렬 분석은 subagent에 위임
- subagent당 하나의 명확한 목표

### 3. 자기 개선 루프
- 유저 수정을 받으면: `tasks/lessons.md`에 패턴 기록
- 같은 실수를 방지하는 규칙 작성

### 4. 완료 전 검증
- 동작 증명 없이 완료 처리하지 않는다
- 테스트 실행, 로그 확인, 정상 동작 시연

## Task Management

### 문서 체계
- `tasks/todo.md` — 현재 작업 체크리스트 (완료되면 체크)
- `tasks/devlog.md` — 전체 개발 항목 추적 (Phase별 테이블, 통계)
- `tasks/lessons.md` — 개발 중 배운 교훈 기록
- `tasks/improvements.md` — 개선사항 추적 (P0/P1/P2/P3 우선순위)

## 에러 핸들링 패턴

### 계층별 try/except 격리
- **핵심 기능** (뉴스 수집, 섹터 매핑): 예외 전파 (빠르게 실패)
- **부가 기능** (LLM 요약, 가격 반응 연결): try/except으로 격리, None 반환
- **데이터 저장**: 별도 try/except, 실패해도 메인 흐름 유지

### API 키 없음 조기 반환
```python
if not API_KEY:
    logger.warning("API 키 미설정. 기능 건너뜀.")
    return None
```

## API 통합 패턴

### 재시도 (Retry with Exponential Backoff)
```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.ok:
            break
    except requests.RequestException as e:
        logger.warning("요청 오류 (시도 %d/%d): %s", attempt + 1, MAX_RETRIES, e)
    if attempt < MAX_RETRIES - 1:
        time.sleep(2 ** attempt)
```

### 필수 규칙
- 크롤링: **User-Agent 헤더 필수**
- 외부 API 호출: **timeout 파라미터 필수** (기본 10초)
- LLM API: 더 긴 timeout 허용 (30초)
- 텔레그램: 4096자 제한, 긴 메시지 분할 전송

## 로깅 패턴

- 모듈별 child logger: `logging.getLogger("geolight.module")`
- **print() 금지** — 반드시 logger 사용
- 중복 핸들러 방지: `if logger.handlers: return`

## 캐싱 패턴

### TTL 기준
- 실시간 가격 (유가, 환율): **5분**
- 뉴스 데이터: **4시간**
- 섹터 매핑 사전: **세션 동안 유지**

## Core Principles

- **단순함 우선**: 변경은 최대한 간결하게. 영향 범위 최소화.
- **근본 원인 해결**: 임시 수정 금지. 시니어 개발자 기준.
- **최소 영향**: 필요한 부분만 수정. 버그 유입 방지.
- **실패 격리**: 부가 기능 실패가 핵심 기능에 영향을 주지 않는다.
- **Graceful degradation**: 외부 의존성 실패 시 기능 저하는 허용, 전체 중단은 불허.
