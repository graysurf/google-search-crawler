from __future__ import annotations

from datetime import date
from typing import Iterable, Protocol

from google_search_crawler.core.domain import ArticleObservation


class Source(Protocol):
    name: str

    def collect(self, keyword: str, start_date: date, end_date: date) -> Iterable[ArticleObservation]: ...
