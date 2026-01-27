# Google News URL Resolution (Aggregator → Publisher URL)

## Why this exists

Google News RSS results often contain aggregator URLs under `news.google.com` (e.g. `https://news.google.com/rss/articles/<id>?oc=5`).
These URLs usually do **not** directly redirect to the publisher page, so a “fetch HTML → extract text” pipeline would end up extracting Google News UI HTML (or skipping entirely).

To run full-text extraction against the *publisher* page, we resolve the Google News aggregator URL into the original publisher URL first.

This is implemented in `google_search_crawler/adapters/full_text.py` and integrated into the full-text extraction stage (`google_search_crawler/application/full_text.py`).

## High-level flow

1. Detect Google News URLs (`news.google.com`).
2. Extract the article identifier (`base64_str`) from the URL path.
3. Fetch decoding parameters (`timestamp`, `signature`) from Google News HTML.
4. Call an internal Google endpoint (`batchexecute`) to decode the publisher URL.
5. Continue the normal pipeline:
   - fetch publisher HTML
   - extract readable text
   - store results into `raw_payload.full_text_extraction`

## Step-by-step details

### 1) Extract `base64_str` from the aggregator URL

We support the common Google News patterns:

- `/rss/articles/<base64_str>`
- `/articles/<base64_str>`
- `/read/<base64_str>`

Implementation: `_extract_google_news_base64_str()`.

If the URL does not match these patterns, resolution fails with `google_news_invalid_url`.

### 2) Fetch decoding params (`timestamp` / `signature`)

We request:

`https://news.google.com/rss/articles/{base64_str}`

and parse the returned HTML. In that HTML there is a node like:

```html
<c-wiz>
  <div jscontroller="..." data-n-a-ts="..." data-n-a-sg="..."></div>
</c-wiz>
```

- `data-n-a-ts` → `timestamp`
- `data-n-a-sg` → `signature`

Implementation: `_fetch_google_news_decoding_params()`.

Notes:

- We intentionally prefer the `/rss/articles/` form. Directly hitting `/articles/{base64_str}` is more likely to trigger bot-protection (`429` / “sorry” pages) in headless environments.
- These attributes are not part of an official public API; they can change.

### 3) Decode to publisher URL via `batchexecute` (RPC `Fbv4je`)

We POST to:

`https://news.google.com/_/DotsSplashUi/data/batchexecute`

using a form field `f.req`. The request encodes an RPC call named `Fbv4je` and passes a JSON payload that includes:

- `"garturlreq"` (request type)
- a context array (mostly constants; currently fixed to `US:en`)
- `base64_str`
- `timestamp`
- `signature`

Implementation: `_decode_google_news_url()`.

### 4) Parse the `batchexecute` response

The response usually includes an anti-XSSI prefix:

`)]}'`

We parse the JSON payload that follows, find the entry like:

```json
["wrb.fr","Fbv4je","[\"garturlres\",\"https://publisher.example/...\" ... ]", ...]
```

Then parse the inner JSON string and extract the resolved publisher URL.

Implementation: `_parse_google_news_batchexecute_response()`.

## How it integrates with full-text extraction

### Where resolution is applied

`extract_full_text()` in `google_search_crawler/adapters/full_text.py`:

- If `urlparse(url).netloc.endswith("news.google.com")`:
  - call `resolve_google_news_url()`
  - replace `url` with the resolved publisher URL
  - proceed with `_fetch_html()` and `extract_text_from_html()`

### What gets stored

`google_search_crawler/application/full_text.py` stores a structured record in:

`ArticleObservation.raw_payload["full_text_extraction"]`

This record includes:

- `requested_url` (original URL, possibly `news.google.com`)
- `resolved_url` (publisher URL, if resolution succeeded)
- `status_code`, `content_type`
- `text` and `text_length` (if extracted)
- `error` (if any)
- `extracted_at` (UTC ISO string)

Additionally, if `resolved_url` differs from the original `ArticleObservation.url`, the observation’s `url` field is updated to the resolved publisher URL before persistence.

## Operational caveats

- **Undocumented behavior**: the `batchexecute` RPC is not a public contract; Google can change it any time.
- **Rate limiting / bot protection**: large-scale decoding may require throttling, caching, and retries.
- **Locale context**: the current `garturlreq` context is fixed. If decoding failures appear for specific regions, we may need to align the context with the crawler’s `hl/gl/ceid`.

