from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from google_search_crawler.core.domain import ArticleObservation, RunMetadata


@dataclass(frozen=True, slots=True)
class PersistResult:
    inserted_observations: int
    skipped_observations: int


class Persistor(Protocol):
    name: str

    def persist(
        self, run: RunMetadata, items: Iterable[ArticleObservation], *, artifact_path: str | None
    ) -> PersistResult: ...
