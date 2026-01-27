"""Logging setup helpers."""

from __future__ import annotations

import logging
import os


def setup_logging(log_level: str | None = None, *, force: bool = False) -> None:
    level_name = (
        log_level
        or os.environ.get("GOOGLE_SEARCH_CRAWLER_LOG_LEVEL")
        or os.environ.get("WEB_CRAWLER_LOG_LEVEL")
        or "INFO"
    ).upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=force,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
