from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from google_search_crawler.core.domain import ArticleObservation, CrawlRequest, PublishedAtConfidence, RunMetadata


logger = logging.getLogger(__name__)


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, PublishedAtConfidence):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_run(output_dir: Path, run: RunMetadata, items: Iterable[ArticleObservation]) -> Path:
    run_dir = output_dir / "runs" / run.run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    run_path = run_dir / "run.json"
    items_path = run_dir / "items.jsonl"

    with run_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(run), handle, ensure_ascii=False, indent=2, default=_json_default)
        handle.write("\n")

    with items_path.open("w", encoding="utf-8") as handle:
        item_count = 0
        for item in items:
            handle.write(json.dumps(asdict(item), ensure_ascii=False, default=_json_default))
            handle.write("\n")
            item_count += 1

    logger.info("wrote run artifact run_id=%s items=%d dir=%s", run.run_id, item_count, run_dir)
    return run_dir


def read_run(run_dir: Path) -> RunMetadata:
    run_path = run_dir / "run.json"
    raw = json.loads(run_path.read_text(encoding="utf-8"))
    request_raw = raw["request"]
    request = CrawlRequest(
        keywords=list(request_raw["keywords"]),
        start_date=date.fromisoformat(request_raw["start_date"]),
        end_date=date.fromisoformat(request_raw["end_date"]),
        sources=list(request_raw["sources"]),
        extract_full_text=bool(request_raw.get("extract_full_text", False)),
    )

    finished_at = raw.get("finished_at")
    return RunMetadata(
        run_id=str(raw["run_id"]),
        started_at=datetime.fromisoformat(raw["started_at"]),
        finished_at=datetime.fromisoformat(finished_at) if finished_at else None,
        request=request,
        item_count=int(raw["item_count"]),
    )


def iter_items(run_dir: Path) -> Iterable[ArticleObservation]:
    items_path = run_dir / "items.jsonl"
    with items_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            confidence = PublishedAtConfidence(raw["published_at_confidence"])
            published_at = raw.get("published_at")
            published_text = raw.get("published_text")
            url = raw.get("url")
            summary = raw.get("summary")
            fingerprint = raw.get("fingerprint")

            yield ArticleObservation(
                source=str(raw["source"]),
                keyword=str(raw["keyword"]),
                title=str(raw["title"]),
                url=str(url) if url else None,
                summary=str(summary) if summary else None,
                published_at=date.fromisoformat(published_at) if published_at else None,
                published_text=str(published_text) if published_text else None,
                published_at_confidence=confidence,
                raw_payload=dict(raw.get("raw_payload") or {}),
                collected_at=datetime.fromisoformat(raw["collected_at"]),
                fingerprint=str(fingerprint) if fingerprint else None,
            )
