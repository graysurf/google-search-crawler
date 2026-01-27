from __future__ import annotations

from typing import Iterable

from google_search_crawler.adapters.persist.base import PersistResult
from google_search_crawler.core.domain import ArticleObservation, RunMetadata


class GoogleSheetsPersistor:
    name = "google_sheets"

    def persist(
        self, run: RunMetadata, items: Iterable[ArticleObservation], *, artifact_path: str | None
    ) -> PersistResult:
        raise NotImplementedError("Google Sheets sink is not implemented yet (legacy.py remains the reference).")
