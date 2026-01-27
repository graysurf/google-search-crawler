"""Domain models shared across the system."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class PublishedAtConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CrawlRequest:
    keywords: list[str]
    start_date: date
    end_date: date
    sources: list[str]
    extract_full_text: bool = False


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: str
    started_at: datetime
    finished_at: datetime | None
    request: CrawlRequest
    item_count: int


@dataclass(frozen=True, slots=True)
class ArticleObservation:
    source: str
    keyword: str
    title: str
    url: str | None
    summary: str | None
    published_at: date | None
    published_text: str | None
    published_at_confidence: PublishedAtConfidence
    raw_payload: dict[str, Any]
    collected_at: datetime
    fingerprint: str | None = None

    def with_fingerprint(self, fingerprint: str) -> "ArticleObservation":
        return ArticleObservation(
            source=self.source,
            keyword=self.keyword,
            title=self.title,
            url=self.url,
            summary=self.summary,
            published_at=self.published_at,
            published_text=self.published_text,
            published_at_confidence=self.published_at_confidence,
            raw_payload=self.raw_payload,
            collected_at=self.collected_at,
            fingerprint=fingerprint,
        )
