from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone

from google_search_crawler.adapters.full_text import extract_full_text
from google_search_crawler.core.domain import ArticleObservation
from google_search_crawler.infra.progress_bar import ProgressLineWriter


logger = logging.getLogger(__name__)


def enrich_items_with_full_text(
    items: list[ArticleObservation],
    *,
    timeout_seconds: float = 10.0,
    max_chars: int = 200_000,
) -> list[ArticleObservation]:
    if not items:
        return []

    logger.info("full-text extraction started items=%d", len(items))
    enriched: list[ArticleObservation] = []
    extracted_at = datetime.now(tz=timezone.utc).isoformat()

    total_items = len(items)
    progress = ProgressLineWriter(prefix="[full-text]", total=total_items)
    loaded = 0
    failed = 0
    skipped = 0
    last_filled_for_logs = -1

    for idx, item in enumerate(items, start=1):
        filled_for_logs = min(int(progress.width * (idx / total_items)), progress.width) if total_items else 0
        if not progress.is_enabled() and (idx == 1 or idx == total_items or filled_for_logs != last_filled_for_logs):
            logger.debug(
                "full-text extraction progress %d/%d loaded=%d failed=%d skipped=%d",
                idx,
                total_items,
                loaded,
                failed,
                skipped,
            )
            last_filled_for_logs = filled_for_logs

        if not item.url:
            skipped += 1
            payload = dict(item.raw_payload)
            payload["full_text_extraction"] = {"error": "missing_url", "extracted_at": extracted_at}
            enriched.append(replace(item, raw_payload=payload))
            progress.update(idx, counters={"loaded": loaded, "failed": failed, "skipped": skipped})
            continue

        result = extract_full_text(item.url, timeout_seconds=timeout_seconds, max_chars=max_chars)
        if result.error:
            failed += 1
        else:
            loaded += 1

        payload = dict(item.raw_payload)
        payload["full_text_extraction"] = {**result.to_payload(), "extracted_at": extracted_at}

        new_url = item.url
        if result.resolved_url and result.resolved_url != item.url:
            new_url = result.resolved_url

        enriched.append(replace(item, raw_payload=payload, url=new_url))
        progress.update(idx, counters={"loaded": loaded, "failed": failed, "skipped": skipped})

    progress.finish(counters={"loaded": loaded, "failed": failed, "skipped": skipped})
    logger.info("full-text extraction finished items=%d", len(items))
    return enriched
