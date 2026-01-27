"""URL canonicalization and fingerprinting helpers."""

from __future__ import annotations

import hashlib
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


_DROP_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    query_items = [
        (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key not in _DROP_QUERY_KEYS
    ]
    query = urlencode(sorted(query_items))
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=query,
        fragment="",
    )
    return urlunparse(normalized)


def _normalize_title(title: str) -> str:
    return " ".join(title.strip().lower().split())


def compute_fingerprint(*, source: str, url: str | None, title: str, published_at: date | None) -> str:
    if url:
        base = f"url:{canonicalize_url(url)}"
    else:
        published = published_at.isoformat() if published_at else "unknown-date"
        base = f"fallback:{source}|{_normalize_title(title)}|{published}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
