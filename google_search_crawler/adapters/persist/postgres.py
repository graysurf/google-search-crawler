from __future__ import annotations

import uuid
from typing import Iterable

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from google_search_crawler.adapters.persist.base import PersistResult
from google_search_crawler.core.domain import ArticleObservation, RunMetadata


_REQUIRED_TABLES = ("crawl_runs", "articles", "article_observations")


class PostgresPersistor:
    name = "postgres"

    def __init__(self, database_url: str, *, schema: str | None = None) -> None:
        self._database_url = database_url
        self._schema = schema

    def persist(
        self, run: RunMetadata, items: Iterable[ArticleObservation], *, artifact_path: str | None
    ) -> PersistResult:
        inserted_observations = 0
        skipped_observations = 0

        with psycopg.connect(self._database_url) as conn:
            _set_search_path(conn, self._schema)
            _ensure_schema(conn)

            conn.execute(
                """
                INSERT INTO crawl_runs (run_id, started_at, finished_at, request_json, item_count, artifact_path)
                VALUES (%(run_id)s, %(started_at)s, %(finished_at)s, %(request_json)s, %(item_count)s, %(artifact_path)s)
                ON CONFLICT (run_id) DO UPDATE SET
                  finished_at = EXCLUDED.finished_at,
                  request_json = EXCLUDED.request_json,
                  item_count = EXCLUDED.item_count,
                  artifact_path = EXCLUDED.artifact_path,
                  updated_at = now()
                """,
                {
                    "run_id": run.run_id,
                    "started_at": run.started_at,
                    "finished_at": run.finished_at,
                    "request_json": Jsonb(_serialize_request(run)),
                    "item_count": run.item_count,
                    "artifact_path": artifact_path,
                },
            )

            for item in items:
                if not item.fingerprint:
                    raise ValueError("missing fingerprint for item")

                article_id = _upsert_article(conn, item)
                inserted = _insert_observation(conn, item, article_id=article_id, crawl_run_id=run.run_id)
                if inserted:
                    inserted_observations += 1
                else:
                    skipped_observations += 1

        return PersistResult(
            inserted_observations=inserted_observations,
            skipped_observations=skipped_observations,
        )


def _set_search_path(conn: psycopg.Connection, schema: str | None) -> None:
    if not schema:
        return
    conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))


def _ensure_schema(conn: psycopg.Connection) -> None:
    missing: list[str] = []
    for table in _REQUIRED_TABLES:
        row = conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()
        if not row or row[0] is None:
            missing.append(table)

    if not missing:
        return

    missing_display = ", ".join(missing)
    raise RuntimeError(
        f"missing required tables: {missing_display}. Apply `migrations/001_init.sql` before running persist."
    )


def _serialize_request(run: RunMetadata) -> dict[str, object]:
    request = run.request
    return {
        "keywords": request.keywords,
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "sources": request.sources,
        "extract_full_text": request.extract_full_text,
    }


def _upsert_article(conn: psycopg.Connection, item: ArticleObservation) -> uuid.UUID:
    article_id = uuid.uuid4()
    row = conn.execute(
        """
        INSERT INTO articles (article_id, fingerprint, canonical_url, title, summary, published_at)
        VALUES (%(article_id)s, %(fingerprint)s, %(canonical_url)s, %(title)s, %(summary)s, %(published_at)s)
        ON CONFLICT (fingerprint) DO UPDATE SET
          canonical_url = COALESCE(articles.canonical_url, EXCLUDED.canonical_url),
          title = EXCLUDED.title,
          summary = COALESCE(articles.summary, EXCLUDED.summary),
          published_at = COALESCE(articles.published_at, EXCLUDED.published_at),
          updated_at = now()
        RETURNING article_id
        """,
        {
            "article_id": article_id,
            "fingerprint": item.fingerprint,
            "canonical_url": item.url,
            "title": item.title,
            "summary": item.summary,
            "published_at": item.published_at,
        },
    ).fetchone()
    if not row:
        raise RuntimeError("failed to upsert article")

    article_id_value = row[0]
    if isinstance(article_id_value, uuid.UUID):
        return article_id_value
    return uuid.UUID(str(article_id_value))


def _insert_observation(
    conn: psycopg.Connection, item: ArticleObservation, *, article_id: uuid.UUID, crawl_run_id: str
) -> bool:
    observation_id = uuid.uuid4()
    inserted = conn.execute(
        """
        INSERT INTO article_observations (
          observation_id,
          article_id,
          source,
          keyword,
          url,
          published_text,
          published_at_confidence,
          raw_payload,
          collected_at,
          crawl_run_id
        )
        VALUES (
          %(observation_id)s,
          %(article_id)s,
          %(source)s,
          %(keyword)s,
          %(url)s,
          %(published_text)s,
          %(published_at_confidence)s,
          %(raw_payload)s,
          %(collected_at)s,
          %(crawl_run_id)s
        )
        ON CONFLICT DO NOTHING
        """,
        {
            "observation_id": observation_id,
            "article_id": article_id,
            "source": item.source,
            "keyword": item.keyword,
            "url": item.url,
            "published_text": item.published_text,
            "published_at_confidence": item.published_at_confidence.value,
            "raw_payload": Jsonb(item.raw_payload),
            "collected_at": item.collected_at,
            "crawl_run_id": crawl_run_id,
        },
    ).rowcount
    return bool(inserted)
