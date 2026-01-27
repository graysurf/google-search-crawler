from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from google_search_crawler.adapters.artifacts.jsonl import iter_items, read_run, write_run
from google_search_crawler.core.domain import ArticleObservation, CrawlRequest, PublishedAtConfidence, RunMetadata


@pytest.mark.smoke
def test_write_and_read_run_roundtrip(tmp_path) -> None:
    request = CrawlRequest(
        keywords=["k1"],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 5),
        sources=["google_news"],
    )
    run = RunMetadata(
        run_id="run-1",
        started_at=datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 1, 5, 12, 1, tzinfo=timezone.utc),
        request=request,
        item_count=1,
    )
    item = ArticleObservation(
        source="google_news",
        keyword="k1",
        title="t",
        url="https://example.com",
        summary="s",
        published_at=date(2026, 1, 4),
        published_text="昨天",
        published_at_confidence=PublishedAtConfidence.HIGH,
        raw_payload={"k": "v"},
        collected_at=datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc),
        fingerprint="fp",
    )

    run_dir = write_run(tmp_path, run, [item])
    loaded_run = read_run(run_dir)
    loaded_items = list(iter_items(run_dir))

    assert loaded_run.run_id == run.run_id
    assert loaded_run.item_count == 1
    assert loaded_items[0].fingerprint == "fp"
