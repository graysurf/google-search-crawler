from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Iterable

from google_search_crawler.adapters.sources.base import Source
from google_search_crawler.adapters.sources.google_news import GoogleNewsSource
from google_search_crawler.adapters.sources.ptt_google_search import PttGoogleSearchSource
from google_search_crawler.application.full_text import enrich_items_with_full_text
from google_search_crawler.core.dedupe import compute_fingerprint
from google_search_crawler.core.domain import ArticleObservation, CrawlRequest, RunMetadata


logger = logging.getLogger(__name__)


_SOURCE_REGISTRY: dict[str, type[Source]] = {
    GoogleNewsSource.name: GoogleNewsSource,
    PttGoogleSearchSource.name: PttGoogleSearchSource,
}


def build_sources(source_names: list[str]) -> list[Source]:
    sources: list[Source] = []
    for name in source_names:
        if name not in _SOURCE_REGISTRY:
            raise ValueError(f"unknown source: {name}")
        sources.append(_SOURCE_REGISTRY[name]())
    return sources


def crawl(request: CrawlRequest, *, sources: list[Source]) -> tuple[RunMetadata, list[ArticleObservation]]:
    started_at = datetime.now(tz=timezone.utc)
    run_id = str(uuid.uuid4())
    logger.info(
        "crawl started run_id=%s sources=%s keywords=%s range=%s..%s",
        run_id,
        [s.name for s in sources],
        request.keywords,
        request.start_date,
        request.end_date,
    )

    collected: list[ArticleObservation] = []
    for keyword in request.keywords:
        for source in sources:
            source_items = list(source.collect(keyword, request.start_date, request.end_date))
            logger.debug("collected %d items from %s for %s", len(source_items), source.name, keyword)
            collected.extend(source_items)

    items = _fingerprint_and_dedupe(collected)
    logger.info("crawl collected=%d deduped=%d", len(collected), len(items))

    if request.extract_full_text:
        items = enrich_items_with_full_text(items)

    items.sort(key=_sort_key, reverse=True)

    finished_at = datetime.now(tz=timezone.utc)
    run = RunMetadata(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        request=request,
        item_count=len(items),
    )
    return run, items


def _fingerprint_and_dedupe(items: Iterable[ArticleObservation]) -> list[ArticleObservation]:
    unique_by_fingerprint: dict[str, ArticleObservation] = {}
    for item in items:
        fingerprint = compute_fingerprint(
            source=item.source,
            url=item.url,
            title=item.title,
            published_at=item.published_at,
        )
        if fingerprint in unique_by_fingerprint:
            continue
        unique_by_fingerprint[fingerprint] = item.with_fingerprint(fingerprint)
    return list(unique_by_fingerprint.values())


def _sort_key(item: ArticleObservation) -> tuple[str, str]:
    published = item.published_at.isoformat() if item.published_at else ""
    return published, item.collected_at.isoformat()
