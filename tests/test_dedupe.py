from __future__ import annotations

from datetime import date

import pytest

from google_search_crawler.core.dedupe import canonicalize_url, compute_fingerprint


@pytest.mark.smoke
def test_canonicalize_url_strips_tracking_and_fragment() -> None:
    url = "https://example.com/path?utm_source=x&id=1#frag"
    assert canonicalize_url(url) == "https://example.com/path?id=1"


@pytest.mark.smoke
def test_fingerprint_prefers_url_over_source() -> None:
    fp_a = compute_fingerprint(
        source="source_a",
        url="https://example.com/path?utm_source=x&id=1#frag",
        title="Title A",
        published_at=None,
    )
    fp_b = compute_fingerprint(
        source="source_b",
        url="https://example.com/path?id=1",
        title="Title B",
        published_at=date(2026, 1, 1),
    )
    assert fp_a == fp_b


@pytest.mark.smoke
def test_fingerprint_fallback_includes_source() -> None:
    fp_a = compute_fingerprint(
        source="source_a",
        url=None,
        title="Same Title",
        published_at=date(2026, 1, 1),
    )
    fp_b = compute_fingerprint(
        source="source_b",
        url=None,
        title="Same Title",
        published_at=date(2026, 1, 1),
    )
    assert fp_a != fp_b
