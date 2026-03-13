"""GeoLight 설정 — 환경변수, 섹터 매핑 사전, 임계치 상수."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("geolight.config")

# ── 환경변수 ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 텔레그램 봇 접근 허용 사용자 (쉼표 구분, 비어있으면 제한 없음)
_raw_allowed = os.getenv("TELEGRAM_ALLOWED_USERS", "")
TELEGRAM_ALLOWED_USERS: set[int] = {
    int(uid.strip()) for uid in _raw_allowed.split(",")
    if uid.strip().isdigit()
}

if not TELEGRAM_BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN 미설정. 텔레그램 기능 비활성화.")
if not TELEGRAM_CHAT_ID:
    logger.warning("TELEGRAM_CHAT_ID 미설정. 텔레그램 기능 비활성화.")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY 미설정. LLM 보조 분류 비활성화.")

# ── DB ────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "geolight.db")

# ── Gemini AI ─────────────────────────────────────────────
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MAX_TOKENS = int(os.getenv("GEMINI_MAX_TOKENS", "8192"))
GEMINI_DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_LIMIT", "10"))

# ── 스케줄 간격 (분) ──────────────────────────────────────
NEWS_INTERVAL_MIN = 30
PRICE_INTERVAL_MIN = 5
SCENARIO_INTERVAL_MIN = 60

# ── 지표 공통 설정 ────────────────────────────────────────
INDICATORS = {
    "oil_wti": {
        "ticker": "CL=F",
        "display_name": "WTI 유가",
        "threshold_pct": 7.0,
        "cooldown_min": 60,
    },
    "oil_brent": {
        "ticker": "BZ=F",
        "display_name": "브렌트 유가",
        "threshold_pct": 7.0,
        "cooldown_min": 60,
    },
    "usd_krw": {
        "ticker": "KRW=X",
        "display_name": "USD/KRW 환율",
        "threshold_pct": 2.0,
        "cooldown_min": 60,
    },
    "vix": {
        "ticker": "^VIX",
        "display_name": "VIX 공포지수",
        "threshold_pct": 20.0,
        "cooldown_min": 60,
    },
    "kospi": {
        "ticker": "^KS11",
        "display_name": "KOSPI",
        "threshold_pct": 4.0,
        "cooldown_min": 60,
    },
}

THRESHOLDS = {
    key: {
        "pct": value["threshold_pct"],
        "cooldown_min": value["cooldown_min"],
    }
    for key, value in INDICATORS.items()
}

INDICATOR_DISPLAY_NAMES = {
    key: value["display_name"]
    for key, value in INDICATORS.items()
}

INDICATOR_MEANINGS = {
    "oil_change_pct": "유가가 단기간에 얼마나 급하게 오르거나 내렸는지 보는 지표입니다.",
    "oil_wti_change_pct": "WTI 유가의 단기 변동률입니다. 에너지·항공·화학에 영향이 큽니다.",
    "oil_brent_change_pct": "브렌트유의 단기 변동률입니다. 글로벌 원자재 부담을 볼 때 참고합니다.",
    "usd_krw_change_pct": "원/달러 환율의 단기 변동률입니다. 높아지면 원화 약세, 수입 부담 확대를 뜻합니다.",
    "kospi_change_pct": "코스피 지수의 단기 변동률입니다. 시장 전체 위험 심리를 보여줍니다.",
    "vix": "미국 변동성 지수입니다. 높을수록 시장의 공포와 불안이 크다는 뜻입니다.",
}

# 과거/요약 키 → 실제 입력 키 목록
INDICATOR_ALIASES = {
    "oil_change_pct": ["oil_wti_change_pct", "oil_brent_change_pct"],
}

# ── RSS 피드 소스 ─────────────────────────────────────────
RSS_FEEDS = {
    "bbc_world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "bbc_business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "bbc_asia": "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
    "cnbc_world": "https://www.cnbc.com/id/100727362/device/rss/rss.html",
    "cnbc_economy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "cnbc_asia": "https://www.cnbc.com/id/19832390/device/rss/rss.html",
    "yonhap_en": "https://en.yna.co.kr/RSS/news.xml",
    "hankyung_finance": "https://www.hankyung.com/feed/finance",
    "hankyung_economy": "https://www.hankyung.com/feed/economy",
}

# ── GDELT API ─────────────────────────────────────────────
GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_THEMES = [
    "ECON_OILPRICE",
    "ECON_CURRENCYRESERVES",
    "ECON_INTEREST_RATE",
    "CRISISLEX_C03_WELLBEING_HEALTH",
    "TAX_FNCACT_SANCTIONS",
    "MILITARY",
    "WMD",
    "TERROR",
]

# ── 이벤트 유형 정의 ─────────────────────────────────────
EVENT_TYPES = [
    "oil_surge",        # 유가 급등
    "oil_crash",        # 유가 급락
    "fx_krw_weak",      # 원화 약세 (USD/KRW 급등)
    "fx_krw_strong",    # 원화 강세
    "geopolitical_tension",  # 지정학 긴장 확대
    "geopolitical_ease",     # 지정학 긴장 완화
    "rate_hike",        # 금리 인상 시사
    "rate_cut",         # 금리 인하 시사
    "vix_spike",        # VIX 급등 (공포 확대)
    "vix_drop",         # VIX 급락 (안심 모드)
    "supply_chain",     # 공급망 이슈
    "china_policy",     # 중국 정책 변화
]

# ── 이벤트 분류 키워드 사전 ────────────────────────────────
EVENT_KEYWORDS = {
    "oil_surge": [
        "oil price surge", "oil spike", "oil rally", "crude oil jump",
        "brent surge", "wti surge", "유가 급등", "유가 상승", "원유 급등",
        "oil hits high", "oil soars", "OPEC cut",
    ],
    "oil_crash": [
        "oil price crash", "oil plunge", "oil drops", "crude oil fall",
        "oil tumbles", "유가 급락", "유가 하락", "원유 급락",
        "oil slump", "oil sinks",
    ],
    "fx_krw_weak": [
        "won weakens", "won falls", "won hits low", "usd/krw rise",
        "원화 약세", "원화 급락", "환율 급등", "달러 강세",
        "dollar strengthens", "korean won slides",
    ],
    "fx_krw_strong": [
        "won strengthens", "won rises", "won gains",
        "원화 강세", "원화 상승", "환율 하락", "달러 약세",
    ],
    "geopolitical_tension": [
        "war", "military strike", "invasion", "missile", "sanctions",
        "blockade", "escalation", "conflict", "전쟁", "군사", "봉쇄",
        "확전", "제재", "미사일", "tension rises", "troops deploy",
        "iran", "strait of hormuz", "middle east crisis",
    ],
    "geopolitical_ease": [
        "ceasefire", "peace talks", "de-escalation", "diplomacy",
        "truce", "agreement", "negotiations", "완화", "휴전",
        "평화", "협상", "외교",
    ],
    "rate_hike": [
        "rate hike", "interest rate increase", "fed raises",
        "tightening", "hawkish", "금리 인상", "긴축", "매파",
    ],
    "rate_cut": [
        "rate cut", "interest rate decrease", "fed cuts",
        "easing", "dovish", "금리 인하", "완화", "비둘기파",
    ],
    "vix_spike": [
        "vix surge", "vix spike", "fear index", "volatility jump",
        "VIX 급등", "공포지수", "변동성 확대",
    ],
    "vix_drop": [
        "vix drops", "vix falls", "volatility eases",
        "VIX 하락", "변동성 축소",
    ],
    "supply_chain": [
        "supply chain", "shipping disruption", "port congestion",
        "semiconductor shortage", "공급망", "물류 차질", "반도체 부족",
    ],
    "china_policy": [
        "china stimulus", "china policy", "pboc", "renminbi",
        "중국 부양", "중국 정책", "위안화", "인민은행",
    ],
}

# ── 섹터 매핑 사전 (이벤트 → 수혜/피해 섹터) ──────────────
SECTOR_MAP = {
    "oil_surge": {
        "beneficiary": ["정유", "해운", "탱커", "LNG"],
        "damaged": ["항공", "화학", "소비"],
    },
    "oil_crash": {
        "beneficiary": ["항공", "소비", "여행", "화학"],
        "damaged": ["정유", "에너지", "해운"],
    },
    "fx_krw_weak": {
        "beneficiary": ["반도체", "자동차", "조선", "수출주"],
        "damaged": ["수입주", "내수", "항공"],
    },
    "fx_krw_strong": {
        "beneficiary": ["수입주", "내수", "항공"],
        "damaged": ["반도체", "자동차", "수출주"],
    },
    "geopolitical_tension": {
        "beneficiary": ["방산", "LNG", "에너지", "금"],
        "damaged": ["항공", "여행", "소비", "반도체"],
    },
    "geopolitical_ease": {
        "beneficiary": ["항공", "여행", "소비", "반도체"],
        "damaged": ["방산", "금"],
    },
    "rate_hike": {
        "beneficiary": ["은행", "보험"],
        "damaged": ["성장주", "부동산", "리츠"],
    },
    "rate_cut": {
        "beneficiary": ["성장주", "부동산", "리츠", "바이오"],
        "damaged": ["은행"],
    },
    "vix_spike": {
        "beneficiary": ["인버스 ETF", "금", "국채"],
        "damaged": ["성장주", "소형주", "바이오"],
    },
    "vix_drop": {
        "beneficiary": ["성장주", "소형주", "바이오"],
        "damaged": ["인버스 ETF"],
    },
    "supply_chain": {
        "beneficiary": ["물류", "해운", "대체 공급업체"],
        "damaged": ["자동차", "전자", "반도체"],
    },
    "china_policy": {
        "beneficiary": ["화장품", "엔터", "카지노", "철강"],
        "damaged": [],
    },
}

# ── KRX 섹터별 대표 종목 ──────────────────────────────────
SECTOR_STOCKS = {
    "정유": [
        {"name": "SK이노베이션", "code": "096770"},
        {"name": "S-Oil", "code": "010950"},
        {"name": "GS", "code": "078930"},
    ],
    "해운": [
        {"name": "HMM", "code": "011200"},
        {"name": "팬오션", "code": "028670"},
    ],
    "탱커": [
        {"name": "대한해운", "code": "005880"},
    ],
    "LNG": [
        {"name": "한국가스공사", "code": "036460"},
        {"name": "SK가스", "code": "018670"},
    ],
    "항공": [
        {"name": "대한항공", "code": "003490"},
        {"name": "진에어", "code": "272450"},
    ],
    "화학": [
        {"name": "LG화학", "code": "051910"},
        {"name": "롯데케미칼", "code": "011170"},
    ],
    "소비": [
        {"name": "신세계", "code": "004170"},
        {"name": "이마트", "code": "139480"},
    ],
    "여행": [
        {"name": "하나투어", "code": "039130"},
        {"name": "모두투어", "code": "080160"},
    ],
    "반도체": [
        {"name": "삼성전자", "code": "005930"},
        {"name": "SK하이닉스", "code": "000660"},
    ],
    "자동차": [
        {"name": "현대차", "code": "005380"},
        {"name": "기아", "code": "000270"},
    ],
    "조선": [
        {"name": "HD한국조선해양", "code": "009540"},
        {"name": "삼성중공업", "code": "010140"},
    ],
    "수출주": [
        {"name": "삼성전자", "code": "005930"},
        {"name": "현대차", "code": "005380"},
    ],
    "방산": [
        {"name": "한화에어로스페이스", "code": "012450"},
        {"name": "LIG넥스원", "code": "079550"},
        {"name": "한국항공우주", "code": "047810"},
    ],
    "은행": [
        {"name": "KB금융", "code": "105560"},
        {"name": "신한지주", "code": "055550"},
        {"name": "하나금융지주", "code": "086790"},
    ],
    "보험": [
        {"name": "삼성화재", "code": "000810"},
        {"name": "DB손해보험", "code": "005830"},
    ],
    "성장주": [
        {"name": "카카오", "code": "035720"},
        {"name": "네이버", "code": "035420"},
    ],
    "부동산": [
        {"name": "신한알파리츠", "code": "293940"},
    ],
    "리츠": [
        {"name": "ESR켄달스퀘어리츠", "code": "365550"},
    ],
    "바이오": [
        {"name": "삼성바이오로직스", "code": "207940"},
        {"name": "셀트리온", "code": "068270"},
    ],
    "금": [
        {"name": "KODEX 골드선물(H)", "code": "132030"},
    ],
    "인버스 ETF": [
        {"name": "KODEX 200선물인버스2X", "code": "252670"},
    ],
    "국채": [
        {"name": "KODEX 국채선물10년", "code": "148070"},
    ],
    "물류": [
        {"name": "CJ대한통운", "code": "000120"},
    ],
    "수입주": [
        {"name": "BGF리테일", "code": "282330"},
    ],
    "내수": [
        {"name": "CJ제일제당", "code": "097950"},
        {"name": "오뚜기", "code": "007310"},
    ],
    "전자": [
        {"name": "삼성전기", "code": "009150"},
        {"name": "LG전자", "code": "066570"},
    ],
    "화장품": [
        {"name": "아모레퍼시픽", "code": "090430"},
        {"name": "LG생활건강", "code": "051900"},
    ],
    "엔터": [
        {"name": "하이브", "code": "352820"},
        {"name": "JYP Ent.", "code": "035900"},
    ],
    "카지노": [
        {"name": "GKL", "code": "114090"},
        {"name": "강원랜드", "code": "035250"},
    ],
    "철강": [
        {"name": "POSCO홀딩스", "code": "005490"},
        {"name": "현대제철", "code": "004020"},
    ],
    "에너지": [
        {"name": "한국전력", "code": "015760"},
        {"name": "SK이노베이션", "code": "096770"},
    ],
    "소형주": [
        {"name": "코스닥 대표", "code": ""},
    ],
    "대체 공급업체": [],
}

# ── 시나리오 정의 ─────────────────────────────────────────
SCENARIOS = {
    "escalation": {
        "name": "확전 시나리오",
        "description": "중동/지정학 긴장 확대, 유가 급등, 안전자산 선호",
        "meaning": "전쟁이나 분쟁 리스크가 커지는 구간입니다. 보통 유가와 방산, 에너지 쪽이 강하고 항공·여행·소비는 부담이 커집니다.",
        "exit_signals": [
            "유가 상승세가 꺾이거나 VIX가 빠르게 내려오면 방산·에너지 비중을 먼저 줄입니다.",
            "휴전, 협상 진전, 긴장 완화 뉴스가 나오면 확전 수혜 포지션은 분할로 정리합니다.",
            "단기 급등으로 수익이 난 종목은 한 번에 다 팔지 말고 2~3회로 나눠 익절합니다.",
        ],
        "indicators": {
            "oil_change_pct": (5.0, None),
            "vix": (25.0, None),
            "oil_wti": (85.0, None),       # 절대 수준: 유가 고수준 확인
        },
        "beneficiary_sectors": ["방산", "LNG", "에너지", "정유", "금"],
        "damaged_sectors": ["항공", "여행", "소비", "성장주"],
    },
    "de_escalation": {
        "name": "완화 시나리오",
        "description": "지정학 긴장 완화, 유가 하락, 위험자산 선호 복귀",
        "meaning": "전쟁이나 지정학 리스크가 누그러지는 구간입니다. 항공·여행·소비처럼 눌렸던 섹터가 회복하기 쉬운 흐름입니다.",
        "exit_signals": [
            "유가가 다시 급반등하거나 VIX가 재상승하면 여행·소비 회복주 비중을 줄입니다.",
            "전쟁 재확대 헤드라인이 나오면 완화 시나리오 전제는 약해지므로 분할 회수합니다.",
            "단기 반등 후 거래대금이 줄면 일부 익절해 현금 비중을 다시 확보합니다.",
        ],
        "indicators": {"oil_change_pct": (None, -5.0), "vix": (None, 20.0)},
        "beneficiary_sectors": ["항공", "여행", "소비", "성장주", "바이오"],
        "damaged_sectors": ["방산"],
    },
    "market_shock": {
        "name": "시장 쇼크 시나리오",
        "description": "코스피 급락, 원화 약세, 과매도 대형주 반등 후보",
        "meaning": "시장 전체가 급하게 흔들리는 구간입니다. 지수 급락과 환율 불안이 같이 오면 방어가 우선이고, 반등은 분할로 접근해야 합니다.",
        "exit_signals": [
            "코스피가 반등하고 환율이 안정되면 과매도 반등분은 일부 회수합니다.",
            "환율 불안이 계속되면 반등 기대 포지션을 더 늘리지 말고 비중을 줄입니다.",
            "반등 없이 추가 하락이 이어지면 손절 기준을 미리 정한 범위에서 실행합니다.",
        ],
        "indicators": {
            "kospi_change_pct": (None, -3.0),
            "usd_krw_change_pct": (1.5, None),
            "vix": (28.0, None),            # 절대 수준: 공포 확인
        },
        "beneficiary_sectors": ["반도체", "자동차", "은행"],
        "damaged_sectors": ["소형주", "바이오", "성장주"],
    },
    "rate_tightening": {
        "name": "긴축 시나리오",
        "description": "미국 금리 인상 기조, 달러 강세, 금융주 수혜",
        "meaning": "금리가 높은 쪽으로 가는 구간입니다. 성장주에는 부담이 되고 은행·보험 같은 금융주는 상대적으로 유리할 수 있습니다.",
        "exit_signals": [
            "금리 인하 기대가 다시 커지면 금융주 중심 포지션은 분할 축소합니다.",
            "달러 강세가 꺾이면 수출·금융 수혜 논리가 약해질 수 있어 일부 회수합니다.",
            "실적 확인 없이 밸류만 급하게 오른 종목은 비중을 줄여 수익을 확정합니다.",
        ],
        "indicators": {
            "vix": (None, 25.0),
            "usd_krw_change_pct": (1.0, None),
            "usd_krw": (1350.0, None),     # 절대 수준: 원화 약세 확인
        },
        "beneficiary_sectors": ["은행", "보험", "수출주"],
        "damaged_sectors": ["성장주", "부동산", "리츠"],
    },
    "rate_easing": {
        "name": "완화 시나리오 (금리)",
        "description": "금리 인하 기대, 유동성 확대, 성장주 수혜",
        "meaning": "금리 부담이 줄어드는 구간입니다. 성장주와 바이오처럼 밸류에이션 민감한 자산이 상대적으로 숨통이 트이는 흐름입니다.",
        "exit_signals": [
            "장기금리가 다시 오르거나 VIX가 반등하면 성장주 비중을 줄입니다.",
            "금리 인하 기대가 후퇴하면 밸류 민감주 수익분부터 먼저 회수합니다.",
            "급등 구간에서는 한 번에 매도하지 말고 2~3회로 나눠 익절합니다.",
        ],
        "indicators": {"vix": (None, 18.0)},
        "beneficiary_sectors": ["성장주", "부동산", "리츠", "바이오"],
        "damaged_sectors": ["은행"],
    },
}

# ── Action Engine 설정 ────────────────────────────────────

# 위험 점수 규칙: (지표 조건, 점수)
ACTION_RISK_RULES = [
    # 유가 급등
    {"indicator": "oil_wti_change_pct", "condition": ">=", "value": 7.0, "score": 2, "reason": "WTI 유가 급등"},
    {"indicator": "oil_brent_change_pct", "condition": ">=", "value": 7.0, "score": 2, "reason": "브렌트유 급등"},
    # 유가 급락 (기회)
    {"indicator": "oil_wti_change_pct", "condition": "<=", "value": -7.0, "score": -1, "reason": "유가 급락 (원가 부담 감소)"},
    # 환율 급등
    {"indicator": "usd_krw_change_pct", "condition": ">=", "value": 1.5, "score": 2, "reason": "원화 약세 (환율 급등)"},
    {"indicator": "usd_krw_change_pct", "condition": ">=", "value": 2.5, "score": 1, "reason": "원화 급락 (추가 위험)"},
    # 환율 안정
    {"indicator": "usd_krw_change_pct", "condition": "<=", "value": -1.0, "score": -1, "reason": "원화 강세 (안정 신호)"},
    # VIX
    {"indicator": "vix", "condition": ">=", "value": 30.0, "score": 3, "reason": "VIX 공포 구간 (30 이상)"},
    {"indicator": "vix", "condition": ">=", "value": 25.0, "score": 1, "reason": "VIX 경계 구간 (25 이상)"},
    {"indicator": "vix", "condition": "<=", "value": 15.0, "score": -2, "reason": "VIX 안정 구간 (15 이하)"},
    # KOSPI
    {"indicator": "kospi_change_pct", "condition": "<=", "value": -3.0, "score": 3, "reason": "KOSPI 급락"},
    {"indicator": "kospi_change_pct", "condition": ">=", "value": 2.0, "score": -1, "reason": "KOSPI 상승 (심리 개선)"},
]

# 시나리오별 위험 점수 가산
ACTION_SCENARIO_SCORES = {
    "escalation": 3,        # 확전 → 위험 +3
    "market_shock": 3,      # 쇼크 → 위험 +3
    "rate_tightening": 1,   # 긴축 → 위험 +1
    "de_escalation": -2,    # 완화 → 위험 -2
    "rate_easing": -2,      # 금리완화 → 위험 -2
}

# 행동 모드 정의 (위험 점수 범위 → 모드)
ACTION_MODES = {
    "hold": {
        "name": "관망",
        "min_score": 6,
        "emoji": "🔴",
        "description": "불확실성이 높아 신규 진입을 자제하는 구간",
        "budget_ratio": (0, 10),
        "guide": "신규 매수 보류 / 기존 보유 유지 / 현금 비중 확대",
    },
    "conservative_dca": {
        "name": "보수적 분할매수",
        "min_score": 4,
        "emoji": "🟠",
        "description": "소액만 천천히 진입하는 구간",
        "budget_ratio": (10, 25),
        "guide": "투자예산의 10~25%만 소액 분할 진입",
    },
    "normal_dca": {
        "name": "일반 분할매수",
        "min_score": 2,
        "emoji": "🟡",
        "description": "시장 스트레스가 완화되어 점진적 진입 가능",
        "budget_ratio": (25, 50),
        "guide": "투자예산의 25~50% 분할 집행",
    },
    "rebalance": {
        "name": "리밸런싱",
        "min_score": None,  # 특수 조건으로 판단
        "emoji": "🔵",
        "description": "과열/왜곡 섹터 비중 조정 구간",
        "budget_ratio": (20, 40),
        "guide": "과열 섹터 축소 / 소외 섹터 분할 진입",
    },
    "aggressive": {
        "name": "적극 진입",
        "min_score": None,  # 위험 점수 1 이하 + 완화 시나리오
        "emoji": "🟢",
        "description": "변동성 안정 + 완화 신호로 적극 진입 가능",
        "budget_ratio": (50, 80),
        "guide": "분할 규칙 유지하되 투자예산의 50~80% 집행 가능",
    },
}

# 행동 모드 쿨다운 (같은 모드 유지 최소 시간)
ACTION_COOLDOWN_HOURS = 6

# 예산 배분: 투자 성향별 비율 조정 계수
BUDGET_PROFILE_MULTIPLIER = {
    "conservative": 0.7,   # 보수: 기본 비율의 70%
    "neutral": 1.0,        # 중립: 기본 비율 그대로
    "aggressive": 1.3,     # 공격: 기본 비율의 130%
}

PROFILE_NAMES = {
    "conservative": "보수",
    "neutral": "중립",
    "aggressive": "공격",
}

PROFILE_ALIASES = {
    "보수": "conservative",
    "보수적": "conservative",
    "중립": "neutral",
    "공격": "aggressive",
    "공격적": "aggressive",
}

ACTION_MODE_FLOW = [
    "aggressive",
    "normal_dca",
    "conservative_dca",
    "hold",
]

ACTION_AGGRESSIVE_SCENARIOS = {
    "de_escalation",
    "rate_easing",
}

ACTION_EVENT_BUCKETS = {
    "tension": {"geopolitical_tension", "oil_surge", "vix_spike", "fx_krw_weak"},
    "ease": {"geopolitical_ease", "oil_crash", "vix_drop", "rate_cut", "fx_krw_strong"},
}

ACTION_URGENT_RULES = [
    {"indicator": "vix", "abs": False, "threshold": 30.0},
    {"indicator": "usd_krw_change_pct", "abs": True, "threshold": 2.0},
    {"indicator": "oil_wti_change_pct", "abs": True, "threshold": 5.0},
    {"indicator": "kospi_change_pct", "abs": True, "threshold": 3.0},
]

# ── 텔레그램 메시지 제한 ──────────────────────────────────
TELEGRAM_MAX_LENGTH = 4096
