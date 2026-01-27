from __future__ import annotations

from datetime import date

import pytest

from google_search_crawler.adapters.sources.google_news_rss import (
    extract_text_summary,
    parse_pub_date_to_datetime,
    parse_rss,
)


@pytest.mark.smoke
def test_parse_rss_extracts_item_fields() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Example Title</title>
      <link>https://news.google.com/rss/articles/example?oc=5</link>
      <pubDate>Sun, 04 Jan 2026 03:56:34 GMT</pubDate>
      <description><![CDATA[<b>Hello</b> world]]></description>
      <source url="https://example.com">Example</source>
    </item>
  </channel>
</rss>
"""
    items = parse_rss(xml)
    assert len(items) == 1
    assert items[0].title == "Example Title"
    assert items[0].link == "https://news.google.com/rss/articles/example?oc=5"
    assert items[0].pub_date == "Sun, 04 Jan 2026 03:56:34 GMT"
    assert items[0].source == "Example"
    assert items[0].source_url == "https://example.com"

    summary = extract_text_summary(items[0].description_html)
    assert summary == "Hello world"

    pub_dt = parse_pub_date_to_datetime(items[0].pub_date)
    assert pub_dt is not None
    assert pub_dt.date() == date(2026, 1, 4)
