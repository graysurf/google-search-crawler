"""Legacy Google Search HTML parser (may break due to bot protection)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from time import sleep
from typing import Iterable

from bs4 import BeautifulSoup
from requests import get


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.62",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0",
]


@dataclass(frozen=True, slots=True)
class SearchResult:
    url: str
    title: str
    description: str


def _request(term: str, *, results: int, lang: str, start: int, timeout: float) -> str:
    resp = get(
        url="https://www.google.com/search",
        headers={"User-Agent": random.choice(_USER_AGENTS)},
        params={"q": term, "num": str(results + 2), "hl": lang, "start": str(start)},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text


def search(
    term: str,
    *,
    num_results: int = 10,
    lang: str = "en",
    sleep_interval: float = 0.0,
    timeout: float = 5.0,
) -> Iterable[SearchResult]:
    start = 0
    while start < num_results:
        html = _request(term, results=num_results - start, lang=lang, start=start, timeout=timeout)
        soup = BeautifulSoup(html, "html.parser")
        result_blocks = soup.find_all("div", attrs={"class": "g"})
        if not result_blocks:
            return

        for result in result_blocks:
            link = result.find("a", href=True)
            title = result.find("h3")
            description_box = result.find("div", {"style": "-webkit-line-clamp:2"})
            if not description_box:
                continue

            description = description_box.text
            if not (link and title and description):
                continue

            href = link.get("href")
            if not href:
                continue

            start += 1
            yield SearchResult(url=str(href), title=title.text, description=description)

        sleep(sleep_interval)
