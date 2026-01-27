from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from google_search_crawler.adapters.artifacts.jsonl import iter_items, read_run, write_run
from google_search_crawler.adapters.persist.postgres import PostgresPersistor
from google_search_crawler.application.pipeline import build_sources, crawl
from google_search_crawler.core.domain import CrawlRequest
from google_search_crawler.infra.config import AppConfig, env_bool
from google_search_crawler.infra.logging_utils import setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="google_search_crawler")
    parser.add_argument("--log-level", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    crawl_parser = sub.add_parser("crawl")
    crawl_parser.add_argument("--keyword", action="append", required=True)
    crawl_parser.add_argument("--start-date", required=True)
    crawl_parser.add_argument("--end-date", required=True)
    crawl_parser.add_argument("--source", action="append", default=["google_news", "ptt"])
    crawl_parser.add_argument(
        "--extract-full-text",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Extract full text per item (default can be set via GOOGLE_SEARCH_CRAWLER_EXTRACT_FULL_TEXT"
            " / WEB_CRAWLER_EXTRACT_FULL_TEXT)."
        ),
    )

    persist_parser = sub.add_parser("persist")
    persist_parser.add_argument("--run-dir", required=True)
    persist_parser.add_argument("--sink", action="append", default=["postgres"])

    api_parser = sub.add_parser("api")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    setup_logging(args.log_level, force=True)
    config = AppConfig.from_env()

    if args.command == "crawl":
        extract_full_text_default = env_bool(
            "GOOGLE_SEARCH_CRAWLER_EXTRACT_FULL_TEXT",
            aliases=["WEB_CRAWLER_EXTRACT_FULL_TEXT"],
            default=False,
        )
        extract_full_text = (
            extract_full_text_default if args.extract_full_text is None else bool(args.extract_full_text)
        )
        request = CrawlRequest(
            keywords=args.keyword,
            start_date=_parse_date(args.start_date),
            end_date=_parse_date(args.end_date),
            sources=args.source,
            extract_full_text=extract_full_text,
        )
        sources = build_sources(args.source)
        run, items = crawl(request, sources=sources)
        run_dir = write_run(config.output_dir, run, items)
        print(run_dir)
        return 0

    if args.command == "persist":
        sinks = set(args.sink)
        if sinks != {"postgres"}:
            raise SystemExit("only 'postgres' sink is implemented in MVP")
        if not config.database_url:
            raise SystemExit("GOOGLE_SEARCH_CRAWLER_DATABASE_URL / WEB_CRAWLER_DATABASE_URL is not configured")

        run_dir = Path(args.run_dir)
        run = read_run(run_dir)
        items = list(iter_items(run_dir))

        result = PostgresPersistor(config.database_url, schema=config.database_schema).persist(
            run, items, artifact_path=str(run_dir)
        )
        print(
            f"inserted_observations={result.inserted_observations} skipped_observations={result.skipped_observations}"
        )
        if result.inserted_observations == 0:
            return 1
        return 0

    if args.command == "api":
        import uvicorn

        uvicorn.run(
            "google_search_crawler.adapters.api.app:app",
            host=args.host,
            port=args.port,
            log_level=(
                args.log_level
                or os.environ.get("GOOGLE_SEARCH_CRAWLER_LOG_LEVEL")
                or os.environ.get("WEB_CRAWLER_LOG_LEVEL")
                or "info"
            ).lower(),
        )
        return 0

    raise SystemExit(f"unknown command: {args.command}")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
