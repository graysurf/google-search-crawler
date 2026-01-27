# Google Search Crawler

Google Search Crawler is a small crawl pipeline that:

- collects article observations from multiple sources,
- writes JSON artifacts (`output/runs/<run_id>/run.json` + `items.jsonl`),
- persists into Postgres,
- exposes a small FastAPI app for triggering crawl and querying stored items.

## Structure

```text
.
├── google_search_crawler/      # Python package (CLI / API)
│   ├── adapters/               # IO boundaries (API / sources / persistence)
│   │   ├── api/                # FastAPI request/response layer
│   │   ├── artifacts/          # JSON artifacts read/write
│   │   ├── persist/            # Persistence sinks (e.g. Postgres)
│   │   └── sources/            # Crawl sources (e.g. Google News, PTT)
│   ├── application/            # Use-cases / pipeline orchestration
│   ├── core/                   # Domain + pure utilities
│   └── infra/                  # Config/logging/progress/vault plumbing
├── migrations/                 # SQL migrations (init schema)
├── tests/                      # Test suite (smoke tests)
├── docs/                       # Project docs
├── output/                     # Generated run artifacts (gitignored)
├── .envrc                      # Optional: direnv helpers for local env
├── requirements.txt            # Runtime dependencies
└── requirements-dev.txt        # Dev dependencies
```

## Requirements

- Python 3.10+
- Postgres (schema applied via `migrations/001_init.sql`)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

## Configure environment

Minimum required for Postgres persistence:

- `GOOGLE_SEARCH_CRAWLER_DATABASE_URL` (recommended), and optionally `GOOGLE_SEARCH_CRAWLER_DB_SCHEMA`

Or build the URL from parts:

- `GOOGLE_SEARCH_CRAWLER_PGHOST`
- `GOOGLE_SEARCH_CRAWLER_PGPORT`
- `GOOGLE_SEARCH_CRAWLER_PGUSER`
- `GOOGLE_SEARCH_CRAWLER_PGPASSWORD`
- `GOOGLE_SEARCH_CRAWLER_PGDATABASE`
- `GOOGLE_SEARCH_CRAWLER_PGSSLMODE` (optional)

Other useful flags:

- `GOOGLE_SEARCH_CRAWLER_OUTPUT_DIR` (default: `output`)
- `GOOGLE_SEARCH_CRAWLER_LOG_LEVEL` (e.g. `INFO` / `DEBUG`)
- `GOOGLE_SEARCH_CRAWLER_EXTRACT_FULL_TEXT` (`1`/`0`, default: `0`)

Legacy env var prefix `WEB_CRAWLER_*` is still accepted for backwards compatibility.

Vault mode (optional):

- When `VAULT_HOST` is set, DB config is loaded from Vault instead of local env.

## Apply database schema (manual migration)

`migrations/001_init.sql` uses a psql variable `google_search_crawler_schema`.
If you don't set it, it defaults to `finance_report_staging` (to match the `fr-psql` environment).

Example:

```bash
psql "$GOOGLE_SEARCH_CRAWLER_DATABASE_URL" -v google_search_crawler_schema=public -f migrations/001_init.sql
```

## Quickstart (CLI)

### Crawl → JSON artifacts

```bash
python -m google_search_crawler crawl \
  --keyword '"iPhone"' \
  --start-date 2026-01-01 \
  --end-date 2026-01-05
```

This prints the run directory (e.g. `output/runs/<run_id>`).

To enable full-text extraction for this run:

```bash
python -m google_search_crawler crawl \
  --keyword '"iPhone"' \
  --start-date 2026-01-01 \
  --end-date 2026-01-05 \
  --extract-full-text
```

### Persist JSON artifacts → Postgres

```bash
python -m google_search_crawler persist --run-dir output/runs/<run_id>
```

## Quickstart (API)

Run the server:

```bash
python -m google_search_crawler api --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl -s http://127.0.0.1:8000/health
```

Trigger a crawl:

```bash
curl -s -X POST http://127.0.0.1:8000/crawl \\
  -H 'Content-Type: application/json' \\
  -d '{\"keywords\":[\"\\\"iPhone\\\"\"],\"start_date\":\"2026-01-01\",\"end_date\":\"2026-01-05\",\"sources\":[\"google_news\",\"ptt\"],\"extract_full_text\":true}'
```

Persist a run:

```bash
curl -s -X POST http://127.0.0.1:8000/persist \\
  -H 'Content-Type: application/json' \\
  -d '{\"run_dir\":\"output/runs/<run_id>\",\"sinks\":[\"postgres\"]}'
```

Query stored articles:

```bash
curl -s 'http://127.0.0.1:8000/articles?keyword=%22%E6%9F%AF%E6%96%87%E5%93%B2%22&limit=10&offset=0'
```

## Dev checks

```bash
ruff check .
ruff format .
mypy
pytest -m smoke
```
