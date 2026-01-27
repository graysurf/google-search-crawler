"""HTML full-text extraction adapter (sync, best-effort).

This module intentionally keeps the implementation lightweight:
- Fetch HTML via `requests`
- Extract readable text via `BeautifulSoup`

It is designed to enrich `ArticleObservation.raw_payload` so persistence remains schema-free.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_BATCHEXECUTE_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
_GOOGLE_NEWS_GARTURLREQ_CONTEXT: list[Any] = [
    ["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
    "X",
    "X",
    1,
    [1, 1, 1],
    1,
    1,
    None,
    0,
    0,
    None,
    0,
]


@dataclass(frozen=True, slots=True)
class FullTextExtractionResult:
    requested_url: str
    resolved_url: str | None
    status_code: int | None
    content_type: str | None
    text: str | None
    error: str | None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "requested_url": self.requested_url,
            "resolved_url": self.resolved_url,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "error": self.error,
        }
        if self.text is not None:
            payload["text"] = self.text
            payload["text_length"] = len(self.text)
        return payload


def extract_full_text(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    max_chars: int = 200_000,
    user_agent: str | None = None,
) -> FullTextExtractionResult:
    requested_url = url
    parsed = urlparse(url)
    if parsed.netloc.endswith("news.google.com"):
        resolved_url, error = resolve_google_news_url(url, timeout_seconds=timeout_seconds, user_agent=user_agent)
        if error or not resolved_url:
            return FullTextExtractionResult(
                requested_url=requested_url,
                resolved_url=None,
                status_code=None,
                content_type=None,
                text=None,
                error=error or "google_news_url_resolution_failed",
            )
        url = resolved_url

    html, resolved_url, status_code, content_type, error = _fetch_html(
        url,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
    )
    if error or html is None:
        return FullTextExtractionResult(
            requested_url=url,
            resolved_url=resolved_url,
            status_code=status_code,
            content_type=content_type,
            text=None,
            error=error or "unknown_fetch_error",
        )

    if content_type and "text/html" not in content_type:
        return FullTextExtractionResult(
            requested_url=url,
            resolved_url=resolved_url,
            status_code=status_code,
            content_type=content_type,
            text=None,
            error="non_html_response",
        )

    text = extract_text_from_html(html)
    if not text:
        return FullTextExtractionResult(
            requested_url=url,
            resolved_url=resolved_url,
            status_code=status_code,
            content_type=content_type,
            text=None,
            error="no_text_extracted",
        )

    if len(text) > max_chars:
        text = text[:max_chars]

    return FullTextExtractionResult(
        requested_url=requested_url,
        resolved_url=resolved_url,
        status_code=status_code,
        content_type=content_type,
        text=text,
        error=None,
    )


def extract_text_from_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for el in soup(["script", "style", "noscript", "svg"]):
        el.decompose()

    candidates: list[str] = []
    for tag_name in ("article", "main"):
        for container in soup.find_all(tag_name):
            candidates.append(_extract_text_from_container(container))

    if soup.body is not None:
        candidates.append(_extract_text_from_container(soup.body))
    else:
        candidates.append(_extract_text_from_container(soup))

    best = max(candidates, key=len, default="")
    normalized = _normalize_text(best)
    if len(normalized) < 200:
        return None
    return normalized


def _fetch_html(
    url: str,
    *,
    timeout_seconds: float,
    user_agent: str | None,
) -> tuple[str | None, str | None, int | None, str | None, str | None]:
    headers = {
        "User-Agent": user_agent or _DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout_seconds, allow_redirects=True)
    except requests.RequestException as exc:
        return None, None, None, None, f"request_failed:{type(exc).__name__}"

    content_type = resp.headers.get("content-type")
    if resp.status_code >= 400:
        return None, resp.url, resp.status_code, content_type, f"http_error:{resp.status_code}"

    return resp.text, resp.url, resp.status_code, content_type, None


def _extract_text_from_container(container: Any) -> str:
    parts: list[str] = []
    for el in container.find_all(["h1", "h2", "h3", "p", "li"]):
        text = el.get_text(" ", strip=True)
        if text:
            parts.append(text)

    if parts:
        return "\n".join(parts)
    return container.get_text(" ", strip=True) if hasattr(container, "get_text") else ""


def _normalize_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def resolve_google_news_url(
    url: str,
    *,
    timeout_seconds: float = 10.0,
    user_agent: str | None = None,
) -> tuple[str | None, str | None]:
    base64_str = _extract_google_news_base64_str(url)
    if not base64_str:
        return None, "google_news_invalid_url"

    timestamp, signature, error = _fetch_google_news_decoding_params(
        base64_str,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
    )
    if error or not timestamp or not signature:
        return None, error or "google_news_decode_params_missing"

    resolved_url, error = _decode_google_news_url(
        base64_str,
        timestamp=timestamp,
        signature=signature,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
    )
    if error:
        return None, error
    return resolved_url, None


def _extract_google_news_base64_str(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.netloc.endswith("news.google.com"):
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    if parts[-2] not in {"articles", "read"}:
        return None
    base64_str = parts[-1].strip()
    return base64_str or None


def _fetch_google_news_decoding_params(
    base64_str: str,
    *,
    timeout_seconds: float,
    user_agent: str | None,
) -> tuple[int | None, str | None, str | None]:
    headers = {"User-Agent": user_agent or _DEFAULT_USER_AGENT}
    url = f"https://news.google.com/rss/articles/{base64_str}"

    try:
        resp = requests.get(url, headers=headers, timeout=timeout_seconds, allow_redirects=True)
    except requests.RequestException as exc:
        return None, None, f"google_news_decode_params_request_failed:{type(exc).__name__}"

    if resp.status_code >= 400:
        return None, None, f"google_news_decode_params_http_error:{resp.status_code}"

    soup = BeautifulSoup(resp.text, "html.parser")
    el = soup.select_one("c-wiz > div[jscontroller]")
    if el is None:
        return None, None, "google_news_decode_params_not_found"

    signature_raw = el.get("data-n-a-sg")
    timestamp_raw = el.get("data-n-a-ts")
    signature = str(signature_raw) if signature_raw else None
    timestamp_text = str(timestamp_raw) if timestamp_raw else None
    if not signature or not timestamp_text:
        return None, None, "google_news_decode_params_missing_attrs"

    try:
        timestamp = int(timestamp_text)
    except ValueError:
        return None, None, "google_news_decode_params_invalid_timestamp"

    return timestamp, signature, None


def _decode_google_news_url(
    base64_str: str,
    *,
    timestamp: int,
    signature: str,
    timeout_seconds: float,
    user_agent: str | None,
) -> tuple[str | None, str | None]:
    headers = {
        "User-Agent": user_agent or _DEFAULT_USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    }

    request_payload = [
        "garturlreq",
        _GOOGLE_NEWS_GARTURLREQ_CONTEXT,
        base64_str,
        timestamp,
        signature,
    ]
    f_req_payload = ["Fbv4je", json.dumps(request_payload)]
    data = {"f.req": json.dumps([[f_req_payload]])}

    try:
        resp = requests.post(_GOOGLE_NEWS_BATCHEXECUTE_URL, headers=headers, data=data, timeout=timeout_seconds)
    except requests.RequestException as exc:
        return None, f"google_news_decode_request_failed:{type(exc).__name__}"

    if resp.status_code >= 400:
        return None, f"google_news_decode_http_error:{resp.status_code}"

    decoded_url = _parse_google_news_batchexecute_response(resp.text)
    if not decoded_url:
        logger.debug("failed to parse google news batchexecute response base64_str=%s", base64_str)
        return None, "google_news_decode_response_parse_failed"

    return decoded_url, None


def _parse_google_news_batchexecute_response(text: str) -> str | None:
    if text.startswith(")]}'"):
        parts = text.split("\n\n")
        if len(parts) < 2:
            return None
        json_text = parts[1]
    else:
        json_text = text

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    for entry in parsed:
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        if entry[0] != "wrb.fr" or entry[1] != "Fbv4je":
            continue
        try:
            inner = json.loads(entry[2])
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(inner, list) and len(inner) >= 2 and isinstance(inner[1], str) and inner[1].startswith("http"):
            return inner[1]
        return None

    return None
