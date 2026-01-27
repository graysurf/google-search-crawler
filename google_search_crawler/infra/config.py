"""Configuration loader (env + Vault)."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from psycopg.conninfo import make_conninfo


ENV_PREFIX = "GOOGLE_SEARCH_CRAWLER"
LEGACY_ENV_PREFIX = "WEB_CRAWLER"


def _get_env_text(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    text = value.strip()
    return text or None


def _get_env_text_first(*names: str) -> str | None:
    for name in names:
        value = _get_env_text(name)
        if value is not None:
            return value
    return None


def env_bool(name: str, *, default: bool = False, aliases: Sequence[str] | None = None) -> bool:
    candidates = [name, *(aliases or [])]
    for candidate in candidates:
        raw_value = os.environ.get(candidate)
        if raw_value is None:
            continue
        normalized = raw_value.strip().lower()
        if not normalized:
            continue
        if normalized in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "f", "no", "n", "off"}:
            return False
        raise ValueError(f"{candidate} must be a boolean (got {raw_value!r})")

    return default


@dataclass(frozen=True, slots=True)
class AppConfig:
    output_dir: Path
    database_url: str | None
    database_schema: str | None

    google_sheets_credentials_file: str | None
    google_sheets_workbook_key: str | None
    google_sheets_worksheet: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        output_dir = Path(
            _get_env_text_first(
                f"{ENV_PREFIX}_OUTPUT_DIR",
                f"{LEGACY_ENV_PREFIX}_OUTPUT_DIR",
            )
            or "output"
        )
        database_url: str | None
        database_schema: str | None
        if (os.environ.get("VAULT_HOST") or "").strip():
            from google_search_crawler.infra.vault import load_database_config_from_vault_env

            database_url, database_schema = load_database_config_from_vault_env()
        else:
            database_url = (
                _get_env_text_first(
                    f"{ENV_PREFIX}_DATABASE_URL",
                    f"{LEGACY_ENV_PREFIX}_DATABASE_URL",
                )
                or _build_database_url_from_env()
            )
            database_schema = _get_env_text_first(
                f"{ENV_PREFIX}_DB_SCHEMA",
                f"{LEGACY_ENV_PREFIX}_DB_SCHEMA",
            )

        google_sheets_credentials_file = _get_env_text_first(
            f"{ENV_PREFIX}_GOOGLE_SHEETS_CREDENTIALS_FILE",
            f"{LEGACY_ENV_PREFIX}_GOOGLE_SHEETS_CREDENTIALS_FILE",
        )
        google_sheets_workbook_key = _get_env_text_first(
            f"{ENV_PREFIX}_GOOGLE_SHEETS_WORKBOOK_KEY",
            f"{LEGACY_ENV_PREFIX}_GOOGLE_SHEETS_WORKBOOK_KEY",
        )
        google_sheets_worksheet = (
            _get_env_text_first(
                f"{ENV_PREFIX}_GOOGLE_SHEETS_WORKSHEET",
                f"{LEGACY_ENV_PREFIX}_GOOGLE_SHEETS_WORKSHEET",
            )
            or "每日爬"
        )

        return cls(
            output_dir=output_dir,
            database_url=database_url,
            database_schema=database_schema,
            google_sheets_credentials_file=google_sheets_credentials_file,
            google_sheets_workbook_key=google_sheets_workbook_key,
            google_sheets_worksheet=google_sheets_worksheet,
        )


def _build_database_url_from_env() -> str | None:
    host = _get_env_text_first(f"{ENV_PREFIX}_PGHOST", f"{LEGACY_ENV_PREFIX}_PGHOST")
    port = _get_env_text_first(f"{ENV_PREFIX}_PGPORT", f"{LEGACY_ENV_PREFIX}_PGPORT")
    user = _get_env_text_first(f"{ENV_PREFIX}_PGUSER", f"{LEGACY_ENV_PREFIX}_PGUSER")
    password = _get_env_text_first(f"{ENV_PREFIX}_PGPASSWORD", f"{LEGACY_ENV_PREFIX}_PGPASSWORD")
    database = _get_env_text_first(f"{ENV_PREFIX}_PGDATABASE", f"{LEGACY_ENV_PREFIX}_PGDATABASE")
    sslmode = _get_env_text_first(f"{ENV_PREFIX}_PGSSLMODE", f"{LEGACY_ENV_PREFIX}_PGSSLMODE")

    if not host or not port or not user or not password or not database:
        return None

    kwargs: dict[str, str] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "dbname": database,
    }
    if sslmode:
        kwargs["sslmode"] = sslmode

    return make_conninfo(**kwargs)
