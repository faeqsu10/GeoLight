"""GeoLight SQLite 영속성 레이어."""

import json
import sqlite3
import logging
from typing import Optional

from config import DB_PATH

logger = logging.getLogger("geolight.storage")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """테이블 생성 (멱등)."""
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT UNIQUE,
                summary TEXT,
                published_at TEXT,
                event_type TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_news_url ON news(url);
            CREATE INDEX IF NOT EXISTS idx_news_event ON news(event_type);

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                title TEXT,
                detail TEXT,
                sectors_json TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                indicator TEXT NOT NULL,
                value REAL,
                change_pct REAL,
                message TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);

            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator TEXT NOT NULL,
                value REAL,
                prev_value REAL,
                change_pct REAL,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_price_indicator ON price_snapshots(indicator);
        """)
        conn.commit()
        logger.info("DB 초기화 완료: %s", DB_PATH)
    finally:
        conn.close()


# ── 뉴스 ─────────────────────────────────────────────────

def insert_news(source: str, title: str, url: str,
                summary: str = "", published_at: str = "",
                event_type: str = "") -> bool:
    """뉴스 삽입. 중복(url) 시 무시. 성공 시 True."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO news (source, title, url, summary, published_at, event_type) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (source, title, url, summary, published_at, event_type),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def get_recent_news(limit: int = 20) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM news ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def news_url_exists(url: str) -> bool:
    conn = _connect()
    try:
        row = conn.execute("SELECT 1 FROM news WHERE url = ?", (url,)).fetchone()
        return row is not None
    finally:
        conn.close()


# ── 이벤트 ───────────────────────────────────────────────

def insert_event(event_type: str, title: str, detail: str = "",
                 sectors: Optional[dict] = None) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO events (event_type, title, detail, sectors_json) VALUES (?, ?, ?, ?)",
            (event_type, title, detail, json.dumps(sectors or {}, ensure_ascii=False)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_recent_events(limit: int = 10) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["sectors"] = json.loads(d.pop("sectors_json", "{}"))
            result.append(d)
        return result
    finally:
        conn.close()


# ── 알림 ─────────────────────────────────────────────────

def insert_alert(alert_type: str, indicator: str, value: float,
                 change_pct: float, message: str) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO alerts (alert_type, indicator, value, change_pct, message) "
            "VALUES (?, ?, ?, ?, ?)",
            (alert_type, indicator, value, change_pct, message),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_last_alert(indicator: str) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM alerts WHERE indicator = ? ORDER BY created_at DESC LIMIT 1",
            (indicator,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ── 가격 스냅샷 ──────────────────────────────────────────

def insert_price_snapshot(indicator: str, value: float,
                          prev_value: float, change_pct: float):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO price_snapshots (indicator, value, prev_value, change_pct) "
            "VALUES (?, ?, ?, ?)",
            (indicator, value, prev_value, change_pct),
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_price(indicator: str) -> Optional[dict]:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM price_snapshots WHERE indicator = ? ORDER BY created_at DESC LIMIT 1",
            (indicator,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
