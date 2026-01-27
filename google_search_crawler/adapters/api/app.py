from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from google_search_crawler.adapters.artifacts.jsonl import iter_items, read_run, write_run
from google_search_crawler.adapters.persist.postgres import PostgresPersistor
from google_search_crawler.application.pipeline import build_sources, crawl
from google_search_crawler.core.domain import CrawlRequest
from google_search_crawler.infra.config import AppConfig, env_bool


logger = logging.getLogger(__name__)

app = FastAPI(title="Google Search Crawler")


class CrawlBody(BaseModel):
    keywords: list[str] = Field(min_length=1)
    start_date: date
    end_date: date
    sources: list[str] = Field(default_factory=lambda: ["google_news", "ptt"])
    extract_full_text: bool | None = None


class CrawlResponse(BaseModel):
    run_id: str
    run_dir: str
    item_count: int


class PersistBody(BaseModel):
    run_dir: str
    sinks: list[str] = Field(default_factory=lambda: ["postgres"])


class PersistResponse(BaseModel):
    inserted_observations: int
    skipped_observations: int


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/crawl", response_model=CrawlResponse)
def crawl_endpoint(body: CrawlBody) -> CrawlResponse:
    config = AppConfig.from_env()
    logger.info("api crawl requested sources=%s keywords=%s", body.sources, body.keywords)
    sources = build_sources(body.sources)
    extract_full_text_default = env_bool(
        "GOOGLE_SEARCH_CRAWLER_EXTRACT_FULL_TEXT",
        aliases=["WEB_CRAWLER_EXTRACT_FULL_TEXT"],
        default=False,
    )
    extract_full_text = extract_full_text_default if body.extract_full_text is None else body.extract_full_text
    request = CrawlRequest(
        keywords=body.keywords,
        start_date=body.start_date,
        end_date=body.end_date,
        sources=body.sources,
        extract_full_text=extract_full_text,
    )
    run, items = crawl(request, sources=sources)
    run_dir = write_run(config.output_dir, run, items)
    logger.info("api crawl finished run_id=%s items=%d", run.run_id, run.item_count)
    return CrawlResponse(run_id=run.run_id, run_dir=str(run_dir), item_count=run.item_count)


@app.post("/persist", response_model=PersistResponse)
def persist_endpoint(body: PersistBody) -> PersistResponse:
    config = AppConfig.from_env()
    run_dir = Path(body.run_dir)
    run = read_run(run_dir)
    items = list(iter_items(run_dir))
    logger.info("api persist requested run_id=%s sinks=%s items=%d", run.run_id, body.sinks, len(items))

    if "postgres" not in set(body.sinks):
        raise HTTPException(status_code=400, detail="only 'postgres' sink is implemented in MVP")
    if not config.database_url:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_SEARCH_CRAWLER_DATABASE_URL / WEB_CRAWLER_DATABASE_URL is not configured",
        )

    result = PostgresPersistor(config.database_url, schema=config.database_schema).persist(
        run, items, artifact_path=str(run_dir)
    )
    logger.info(
        "api persist finished run_id=%s inserted=%d skipped=%d",
        run.run_id,
        result.inserted_observations,
        result.skipped_observations,
    )
    return PersistResponse(
        inserted_observations=result.inserted_observations,
        skipped_observations=result.skipped_observations,
    )


@app.get("/articles")
def list_articles(
    keyword: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    config = AppConfig.from_env()
    if not config.database_url:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_SEARCH_CRAWLER_DATABASE_URL / WEB_CRAWLER_DATABASE_URL is not configured",
        )

    import psycopg
    from psycopg import sql as pg_sql
    from psycopg.rows import dict_row

    logger.info("api articles query keyword=%s limit=%d offset=%d", keyword, limit, offset)
    where_parts = ["o.keyword = %(keyword)s"]
    params: dict[str, Any] = {"keyword": keyword, "limit": limit, "offset": offset}
    if start_date:
        where_parts.append("a.published_at >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        where_parts.append("a.published_at <= %(end_date)s")
        params["end_date"] = end_date

    where_sql = " AND ".join(where_parts)
    sql = f"""
      SELECT
        a.fingerprint,
        a.canonical_url,
        a.title,
        a.summary,
        a.published_at,
        o.source,
        o.url,
        o.published_text,
        o.published_at_confidence,
        o.collected_at
      FROM articles a
      JOIN article_observations o ON o.article_id = a.article_id
      WHERE {where_sql}
      ORDER BY a.published_at DESC NULLS LAST, o.collected_at DESC
      LIMIT %(limit)s OFFSET %(offset)s
    """

    with psycopg.connect(config.database_url, row_factory=dict_row) as conn:
        if config.database_schema:
            conn.execute(pg_sql.SQL("SET search_path TO {}, public").format(pg_sql.Identifier(config.database_schema)))
        rows = conn.execute(sql, params).fetchall()
    return {"items": rows, "limit": limit, "offset": offset}
