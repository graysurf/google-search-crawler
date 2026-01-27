from __future__ import annotations

import json

import pytest

from google_search_crawler.adapters.full_text import extract_full_text, extract_text_from_html, resolve_google_news_url


@pytest.mark.smoke
def test_extract_text_from_html_prefers_article_and_strips_scripts() -> None:
    long_body = " ".join(["Hello world."] * 30)
    html = """
    <html>
      <head><title>t</title></head>
      <body>
        <script>console.log("noise")</script>
        <article>
          <h1>Title</h1>
          <p>{long_body}</p>
          <p>Second paragraph.</p>
        </article>
      </body>
    </html>
    """.format(long_body=long_body)
    text = extract_text_from_html(html)
    assert text is not None
    assert "Title" in text
    assert "Hello world." in text
    assert "console.log" not in text


@pytest.mark.smoke
def test_resolve_google_news_url_decodes_via_batchexecute(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __init__(self, *, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text

    captured: dict[str, object] = {}

    def fake_get(url: str, *, headers: dict[str, str], timeout: float, allow_redirects: bool) -> FakeResponse:
        assert url.startswith("https://news.google.com/rss/articles/")
        return FakeResponse(
            status_code=200,
            text=('<c-wiz><div jscontroller="aLI87" data-n-a-ts="123" data-n-a-sg="SIG"></div></c-wiz>'),
        )

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        data: dict[str, str],
        timeout: float,
    ) -> FakeResponse:
        assert url == "https://news.google.com/_/DotsSplashUi/data/batchexecute"
        captured["f.req"] = data["f.req"]
        return FakeResponse(
            status_code=200,
            text=(
                ")]}'\n\n"
                '[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://example.com/article\\"]",null,null,null]]'
                "\n\n"
            ),
        )

    monkeypatch.setattr("google_search_crawler.adapters.full_text.requests.get", fake_get)
    monkeypatch.setattr("google_search_crawler.adapters.full_text.requests.post", fake_post)

    resolved_url, error = resolve_google_news_url("https://news.google.com/rss/articles/BASE64?oc=5", timeout_seconds=1)
    assert error is None
    assert resolved_url == "https://example.com/article"

    outer = json.loads(str(captured["f.req"]))
    assert outer[0][0][0] == "Fbv4je"
    request_payload = json.loads(outer[0][0][1])
    assert request_payload[0] == "garturlreq"
    assert request_payload[2] == "BASE64"
    assert request_payload[3] == 123
    assert request_payload[4] == "SIG"


@pytest.mark.smoke
def test_extract_full_text_resolves_google_news_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    import google_search_crawler.adapters.full_text as full_text

    def fake_resolve(*_args: object, **_kwargs: object) -> tuple[str | None, str | None]:
        return "https://example.com/article", None

    def fake_fetch_html(
        url: str,
        *,
        timeout_seconds: float,
        user_agent: str | None,
    ) -> tuple[str | None, str | None, int | None, str | None, str | None]:
        assert url == "https://example.com/article"
        long_body = " ".join(["Hello world."] * 30)
        html = "<html><body><article><h1>Title</h1><p>" + long_body + "</p></article></body></html>"
        return html, url, 200, "text/html", None

    monkeypatch.setattr(full_text, "resolve_google_news_url", fake_resolve)
    monkeypatch.setattr(full_text, "_fetch_html", fake_fetch_html)

    result = extract_full_text("https://news.google.com/rss/articles/example")
    assert result.error is None
    assert result.text is not None
    assert result.resolved_url == "https://example.com/article"
