# GeoLight - TODO

## 완료된 범위
- [x] 프로젝트 초기 세팅 (Git, 구조, 설정, 로깅)
- [x] 뉴스 수집 파이프라인 (RSS 9개 소스 + GDELT)
- [x] 이벤트 분류 엔진 (규칙 기반 + Gemini 보조)
- [x] 한국장 섹터 매핑 사전 구축
- [x] KRX 대표 종목 데이터 연결
- [x] 시나리오 기반 투자 지도
- [x] 행동 엔진 + 예산 배분
- [x] 임계치 기반 알림 (유가, 환율, VIX, KOSPI)
- [x] 관심 급증 종목 탐색
- [x] 텔레그램 봇 명령 세트
- [x] AI 시장 분석 `/ask`
- [x] 핵심 회귀 테스트 추가
- [x] UX 개선 — format_action_card, format_budget_card 전면 재작성
- [x] Config 중앙화 — ACTION_MODE_FLOW, ACTION_URGENT_RULES 등
- [x] 텔레그램 헬퍼 함수 추가 + 에러 메시지 통일
- [x] 포지션 추적 시스템 (`/portfolio` 명령)

- [x] 조간 브리핑 자동 발송 (08:30)
- [x] fetch_all_prices 병렬화 (1.5초→0.8초)
- [x] 시나리오 절대 수준 조건 + google-generativeai 제거

## 다음 우선순위 (Phase 5)
- [ ] 텔레그램 명령 end-to-end 테스트 보강
- [ ] 웹 대시보드

## Backlog
- [ ] DB/로그 기반 운영 점검 스크립트
- [ ] 데이터 품질 모니터링 (중복 뉴스, 오분류, API 실패율)
- [ ] Signalight 연동 (종목 시그널 교차 참조)
