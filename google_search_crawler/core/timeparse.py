"""Helpers for parsing imperfect published-at fields."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from dateutil import parser

from google_search_crawler.core.domain import PublishedAtConfidence


_DAYS_AGO_RE = re.compile(r"(?P<value>\d+)\s*天前")
_HOURS_AGO_RE = re.compile(r"(?P<value>\d+)\s*小時前")
_MINUTES_AGO_RE = re.compile(r"(?P<value>\d+)\s*分鐘前")


def parse_published_text(published_text: str | None, *, now: datetime) -> tuple[date | None, PublishedAtConfidence]:
    if not published_text:
        return None, PublishedAtConfidence.UNKNOWN

    text = published_text.strip()
    if not text:
        return None, PublishedAtConfidence.UNKNOWN

    if text == "昨天":
        return (now - timedelta(days=1)).date(), PublishedAtConfidence.HIGH

    if match := _DAYS_AGO_RE.search(text):
        days = int(match.group("value"))
        return (now - timedelta(days=days)).date(), PublishedAtConfidence.HIGH

    if match := _HOURS_AGO_RE.search(text):
        hours = int(match.group("value"))
        return (now - timedelta(hours=hours)).date(), PublishedAtConfidence.HIGH

    if match := _MINUTES_AGO_RE.search(text):
        minutes = int(match.group("value"))
        return (now - timedelta(minutes=minutes)).date(), PublishedAtConfidence.HIGH

    normalized = text.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
    try:
        return parser.parse(normalized).date(), PublishedAtConfidence.HIGH
    except (ValueError, OverflowError, TypeError):
        return None, PublishedAtConfidence.UNKNOWN
