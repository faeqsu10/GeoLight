"""뉴스 수집 — GDELT API + RSS 피드."""

import logging
import time
from typing import Optional
from datetime import datetime, timedelta

import requests
import feedparser

from config import RSS_FEEDS, GDELT_API_URL, GDELT_THEMES

logger = logging.getLogger("geolight.data.news")

_USER_AGENT = "GeoLight/1.0 (news-aggregator)"
_TIMEOUT = 15


# ── RSS 수집 ─────────────────────────────────────────────

def fetch_rss_feed(feed_name: str, feed_url: str) -> list[dict]:
    """단일 RSS 피드에서 뉴스 수집."""
    try:
        resp = requests.get(
            feed_url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("RSS 수집 실패 [%s]: %s", feed_name, e)
        return []

    feed = feedparser.parse(resp.content)
    articles = []
    for entry in feed.entries:
        published = ""
        if hasattr(entry, "published"):
            published = entry.published
        elif hasattr(entry, "updated"):
            published = entry.updated

        articles.append({
            "source": feed_name,
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "summary": entry.get("summary", "")[:500],
            "published_at": published,
        })
    logger.info("RSS [%s] %d건 수집", feed_name, len(articles))
    return articles


def fetch_all_rss() -> list[dict]:
    """모든 RSS 피드에서 뉴스 수집."""
    all_articles = []
    for name, url in RSS_FEEDS.items():
        articles = fetch_rss_feed(name, url)
        all_articles.extend(articles)
        time.sleep(0.5)  # 피드 간 간격
    logger.info("전체 RSS %d건 수집", len(all_articles))
    return all_articles


# ── GDELT 수집 ────────────────────────────────────────────

def fetch_gdelt_news(
    query: Optional[str] = None,
    theme: Optional[str] = None,
    max_records: int = 50,
) -> list[dict]:
    """GDELT DOC 2.0 API로 뉴스 수집."""
    params = {
        "mode": "ArtList",
        "maxrecords": str(max_records),
        "format": "json",
        "sort": "DateDesc",
        "timespan": "24h",
    }
    if query:
        params["query"] = query
    elif theme:
        params["query"] = f"theme:{theme}"
    else:
        params["query"] = " OR ".join(f"theme:{t}" for t in GDELT_THEMES[:4])

    try:
        resp = requests.get(
            GDELT_API_URL,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("GDELT 수집 실패: %s", e)
        return []

    articles_raw = data.get("articles", [])
    articles = []
    for art in articles_raw:
        articles.append({
            "source": "gdelt",
            "title": art.get("title", ""),
            "url": art.get("url", ""),
            "summary": art.get("seendate", ""),
            "published_at": art.get("seendate", ""),
        })

    logger.info("GDELT %d건 수집", len(articles))
    return articles


def fetch_gdelt_by_themes() -> list[dict]:
    """주요 GDELT 테마별 뉴스 수집."""
    all_articles = []
    for theme in GDELT_THEMES:
        articles = fetch_gdelt_news(theme=theme, max_records=10)
        all_articles.extend(articles)
        time.sleep(1)  # rate limit 존중
    return all_articles


# ── 통합 수집 ─────────────────────────────────────────────

def collect_all_news() -> list[dict]:
    """RSS + GDELT 모두 수집하여 반환."""
    rss_articles = fetch_all_rss()
    gdelt_articles = fetch_gdelt_by_themes()
    all_articles = rss_articles + gdelt_articles

    # URL 기반 중복 제거
    seen_urls = set()
    unique = []
    for art in all_articles:
        url = art.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(art)

    logger.info("전체 수집 %d건 (중복 제거 후 %d건)", len(all_articles), len(unique))
    return unique
