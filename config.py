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

if not TELEGRAM_BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN 미설정. 텔레그램 기능 비활성화.")
if not TELEGRAM_CHAT_ID:
    logger.warning("TELEGRAM_CHAT_ID 미설정. 텔레그램 기능 비활성화.")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY 미설정. LLM 보조 분류 비활성화.")

# ── DB ────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "geolight.db")

# ── 스케줄 간격 (분) ──────────────────────────────────────
NEWS_INTERVAL_MIN = 30
PRICE_INTERVAL_MIN = 5
SCENARIO_INTERVAL_MIN = 60

# ── 임계치 설정 ──────────────────────────────────────────
THRESHOLDS = {
    "oil_wti": {"pct": 7.0, "cooldown_min": 60},
    "oil_brent": {"pct": 7.0, "cooldown_min": 60},
    "usd_krw": {"pct": 2.0, "cooldown_min": 60},
    "vix": {"pct": 20.0, "cooldown_min": 60},
    "kospi": {"pct": 4.0, "cooldown_min": 60},
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
        "indicators": {"oil_change_pct": (5.0, None), "vix": (25.0, None)},
        "beneficiary_sectors": ["방산", "LNG", "에너지", "정유", "금"],
        "damaged_sectors": ["항공", "여행", "소비", "성장주"],
    },
    "de_escalation": {
        "name": "완화 시나리오",
        "description": "지정학 긴장 완화, 유가 하락, 위험자산 선호 복귀",
        "indicators": {"oil_change_pct": (None, -5.0), "vix": (None, 20.0)},
        "beneficiary_sectors": ["항공", "여행", "소비", "성장주", "바이오"],
        "damaged_sectors": ["방산"],
    },
    "market_shock": {
        "name": "시장 쇼크 시나리오",
        "description": "코스피 급락, 원화 약세, 과매도 대형주 반등 후보",
        "indicators": {"kospi_change_pct": (None, -3.0), "usd_krw_change_pct": (1.5, None)},
        "beneficiary_sectors": ["반도체", "자동차", "은행"],
        "damaged_sectors": ["소형주", "바이오", "성장주"],
    },
    "rate_tightening": {
        "name": "긴축 시나리오",
        "description": "미국 금리 인상 기조, 달러 강세, 금융주 수혜",
        "indicators": {"vix": (None, 25.0), "usd_krw_change_pct": (1.0, None)},
        "beneficiary_sectors": ["은행", "보험", "수출주"],
        "damaged_sectors": ["성장주", "부동산", "리츠"],
    },
    "rate_easing": {
        "name": "완화 시나리오 (금리)",
        "description": "금리 인하 기대, 유동성 확대, 성장주 수혜",
        "indicators": {"vix": (None, 18.0)},
        "beneficiary_sectors": ["성장주", "부동산", "리츠", "바이오"],
        "damaged_sectors": ["은행"],
    },
}

# ── 텔레그램 메시지 제한 ──────────────────────────────────
TELEGRAM_MAX_LENGTH = 4096
