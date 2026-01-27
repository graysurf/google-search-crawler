"""Google News RSS helpers (fetch + parse)."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RssItem:
    title: str
    link: str
    pub_date: str | None
    source: str | None
    source_url: str | None
    description_html: str | None


def fetch_rss(*, query: str, hl: str, gl: str, ceid: str, timeout_seconds: float = 10.0) -> str:
    resp = requests.get(
        "https://news.google.com/rss/search",
        params={"q": query, "hl": hl, "gl": gl, "ceid": ceid},
        timeout=timeout_seconds,
    )
    resp.raise_for_status()
    return resp.text


def parse_rss(xml_text: str) -> list[RssItem]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []

    items: list[RssItem] = []
    for item_el in channel.findall("item"):
        title = (item_el.findtext("title") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        if not title or not link:
            continue

        pub_date = _strip_or_none(item_el.findtext("pubDate"))
        description_html = _strip_or_none(item_el.findtext("description"))
        source_el = item_el.find("source")
        source = _strip_or_none(source_el.text) if source_el is not None else None
        source_url = source_el.attrib.get("url") if source_el is not None else None

        items.append(
            RssItem(
                title=title,
                link=link,
                pub_date=pub_date,
                source=source,
                source_url=source_url,
                description_html=description_html,
            )
        )

    return items


def parse_pub_date_to_datetime(pub_date: str | None) -> datetime | None:
    if not pub_date:
        return None
    try:
        return parsedate_to_datetime(pub_date)
    except (TypeError, ValueError, OverflowError):
        return None


def extract_text_summary(description_html: str | None) -> str | None:
    if not description_html:
        return None
    soup = BeautifulSoup(description_html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return text or None


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def iter_items_for_window(
    *,
    keyword: str,
    after: str,
    before: str,
    hl: str,
    gl: str,
    ceid: str,
) -> Iterable[RssItem]:
    query = f"{keyword} after:{after} before:{before}"
    logger.debug("fetching google news rss query=%s", query)
    xml_text = fetch_rss(query=query, hl=hl, gl=gl, ceid=ceid)
    items = parse_rss(xml_text)
    logger.debug("parsed rss items count=%d window=%s..%s", len(items), after, before)
    return items
