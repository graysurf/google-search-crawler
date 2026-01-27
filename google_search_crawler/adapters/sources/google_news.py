from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from google_search_crawler.adapters.sources.google_news_rss import (
    extract_text_summary,
    iter_items_for_window,
    parse_pub_date_to_datetime,
)
from google_search_crawler.core.domain import ArticleObservation, PublishedAtConfidence


logger = logging.getLogger(__name__)


class GoogleNewsSource:
    name = "google_news"

    def __init__(self, *, hl: str = "zh-TW", gl: str = "TW", ceid: str = "TW:zh-Hant", window_days: int = 3) -> None:
        self._hl = hl
        self._gl = gl
        self._ceid = ceid
        self._window_days = window_days

    def collect(self, keyword: str, start_date: date, end_date: date) -> Iterable[ArticleObservation]:
        cursor = start_date
        keyword_plain = keyword.replace('"', "").strip()
        logger.debug("collect google_news keyword=%s range=%s..%s", keyword, start_date, end_date)

        while cursor < end_date:
            after = cursor.strftime("%Y-%m-%d")
            before = (cursor + timedelta(days=self._window_days)).strftime("%Y-%m-%d")
            items = list(
                iter_items_for_window(
                    keyword=keyword,
                    after=after,
                    before=before,
                    hl=self._hl,
                    gl=self._gl,
                    ceid=self._ceid,
                )
            )
            logger.debug("google_news window=%s..%s rss_items=%d", after, before, len(items))

            collected_at = datetime.now(tz=timezone.utc)
            yielded = 0
            for item in items:
                if keyword_plain and keyword_plain not in item.title:
                    continue

                pub_dt = parse_pub_date_to_datetime(item.pub_date)
                published_at = pub_dt.date() if pub_dt else None
                yield ArticleObservation(
                    source=self.name,
                    keyword=keyword,
                    title=item.title,
                    url=item.link,
                    summary=extract_text_summary(item.description_html),
                    published_at=published_at,
                    published_text=item.pub_date,
                    published_at_confidence=PublishedAtConfidence.HIGH
                    if published_at
                    else PublishedAtConfidence.UNKNOWN,
                    raw_payload={
                        "title": item.title,
                        "link": item.link,
                        "pub_date": item.pub_date,
                        "source": item.source,
                        "source_url": item.source_url,
                        "description_html": item.description_html,
                        "keyword": keyword,
                        "after": after,
                        "before": before,
                    },
                    collected_at=collected_at,
                )
                yielded += 1
            logger.debug("google_news window=%s..%s yielded=%d", after, before, yielded)

            cursor += timedelta(days=self._window_days)
