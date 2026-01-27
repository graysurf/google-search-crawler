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


class PttGoogleSearchSource:
    name = "ptt"

    def __init__(self, *, window_days: int = 7) -> None:
        self._window_days = window_days

    def collect(self, keyword: str, start_date: date, end_date: date) -> Iterable[ArticleObservation]:
        cursor = start_date
        keyword_plain = keyword.replace('"', "").strip()
        keyword_for_query = f"{keyword} site:ptt.cc"
        logger.debug("collect ptt keyword=%s range=%s..%s", keyword, start_date, end_date)

        while cursor < end_date:
            after = cursor.strftime("%Y-%m-%d")
            before = (cursor + timedelta(days=self._window_days)).strftime("%Y-%m-%d")
            items = list(
                iter_items_for_window(
                    keyword=keyword_for_query,
                    after=after,
                    before=before,
                    hl="zh-TW",
                    gl="TW",
                    ceid="TW:zh-Hant",
                )
            )
            logger.debug("ptt window=%s..%s rss_items=%d", after, before, len(items))

            collected_at = datetime.now(tz=timezone.utc)
            yielded = 0
            for item in items:
                if item.source_url and "ptt.cc" not in item.source_url:
                    continue
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
                    published_at_confidence=PublishedAtConfidence.MEDIUM
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
                        "query": keyword_for_query,
                        "after": after,
                        "before": before,
                    },
                    collected_at=collected_at,
                )
                yielded += 1
            logger.debug("ptt window=%s..%s yielded=%d", after, before, yielded)

            cursor += timedelta(days=self._window_days)
