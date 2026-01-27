from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from google_search_crawler.core.domain import PublishedAtConfidence
from google_search_crawler.core.timeparse import parse_published_text


@pytest.mark.smoke
def test_parse_published_text_relative_time() -> None:
    now = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)

    published_at, confidence = parse_published_text("3 天前", now=now)
    assert published_at == date(2026, 1, 2)
    assert confidence == PublishedAtConfidence.HIGH

    published_at, confidence = parse_published_text("1 小時前", now=now)
    assert published_at == date(2026, 1, 5)
    assert confidence == PublishedAtConfidence.HIGH

    published_at, confidence = parse_published_text("15 分鐘前", now=now)
    assert published_at == date(2026, 1, 5)
    assert confidence == PublishedAtConfidence.HIGH

    published_at, confidence = parse_published_text("昨天", now=now)
    assert published_at == date(2026, 1, 4)
    assert confidence == PublishedAtConfidence.HIGH


@pytest.mark.smoke
def test_parse_published_text_absolute_date() -> None:
    now = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)

    published_at, confidence = parse_published_text("2026年1月3日", now=now)
    assert published_at == date(2026, 1, 3)
    assert confidence == PublishedAtConfidence.HIGH

    published_at, confidence = parse_published_text("2026-01-03", now=now)
    assert published_at == date(2026, 1, 3)
    assert confidence == PublishedAtConfidence.HIGH


@pytest.mark.smoke
def test_parse_published_text_empty() -> None:
    now = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
    published_at, confidence = parse_published_text("", now=now)
    assert published_at is None
    assert confidence == PublishedAtConfidence.UNKNOWN
