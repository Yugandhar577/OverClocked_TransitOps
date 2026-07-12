---
name: backend-development-tasks
description: Use when implementing or modifying backend components in
  the Python/FastAPI ingestion and processing pipeline using PostgreSQL,
  Redis Streams, Celery, and NLP tooling.
---

# Skill: Backend Development Tasks

## Stack Reminder

-   Python 3.12, FastAPI, PostgreSQL + pgvector, Redis Streams, Celery,
    spaCy, Sentence-Transformers
-   All modules live under `src/backend/app/`
-   Workers live under `src/backend/workers/`

---

## Module Responsibility Rules

Every module must have a single responsibility. State it in the
module-level docstring:

``` python
"""
app/fetch/http_client.py

Responsibility: Execute HTTP requests with timeout, retry, and User-Agent rotation.
Does not handle robots.txt, rate limiting, or content extraction.
"""
```

If you can't write a one-sentence responsibility, the module is doing
too much.

---

## 1. Database Module (`app/db.py`)

### What it must do

-   Provide an async connection pool (asyncpg preferred)
-   Expose `get_conn()` as an async context manager
-   Handle pool startup and shutdown via FastAPI lifespan

### Pattern

``` python
async def get_conn():
    async with pool.acquire() as conn:
        yield conn
```

### Rules

-   Never open a raw connection outside this module
-   Pool size should come from env var, not hardcoded
-   Always use parameterized queries --- never f-string SQL

---

## 2. Redis Module (`app/redis.py`)

### What it must do

-   Provide a Redis client (redis-py async)
-   Expose stream publish (`xadd`) and consume (`xreadgroup`) helpers
-   Handle consumer group creation idempotently on startup

### Stream names (fixed --- do not rename)

    ingest:urls
    ingest:fetched
    ingest:normalized

-   `ingest:urls` --- URLs to fetch
-   `ingest:fetched` --- raw fetched pages ready for normalization
-   `ingest:normalized` --- normalized articles ready for clustering

### Rules

-   `XACK` must only be called after the downstream operation succeeds
-   Never swallow Redis errors --- log and re-raise
-   Consumer group names: `{stream_name}:workers`

---

## 3. Fetch Modules (`app/fetch/`)

### `http_client.py`

-   Async HTTP with httpx
-   Retry: 3 attempts, exponential backoff
-   Timeout: 10s connect, 30s read
-   Rotate User-Agent headers
-   Return raw bytes + final URL (after redirects) + status code

### `robots.py`

-   Check robots.txt per domain before fetching
-   Cache robots.txt per domain (TTL: 24h in Redis)
-   Return bool: `is_allowed(url, user_agent) -> bool`
-   If robots.txt fetch fails → assume allowed, log warning

### `rate_limit.py`

-   Per-domain rate limiting using Redis token bucket
-   Default: 1 request per 2 seconds per domain
-   Configurable per domain via a config dict
-   Block (async sleep) until token available --- do not skip

### `renderer.py`

-   JS rendering via Playwright (async)
-   Only invoke for URLs flagged as JS-heavy --- not all URLs
-   Timeout: 15s for page load
-   Return rendered HTML string

### `extractor.py`

-   Extract: title, body text, publish date, author, canonical URL
-   Use trafilatura as primary extractor
-   Fallback to BeautifulSoup for sites trafilatura misses
-   Never return None for body --- return empty string and log

---

## 4. RSS Layer (`app/rss/`)

### `feeds.py`

-   Static registry of outlet RSS feed URLs
-   Each entry:
    `{outlet_id, name, feed_url, language, wire_source: bool}`
-   Wire sources (ANI, PTI, Reuters, AP, AFP, IANS) must be flagged
    `wire_source: True`

### `poller.py`

-   Poll all feeds on a schedule (every 10 min default)
-   Parse with feedparser
-   For each entry: check dedupe, then push URL to `ingest:urls` stream
-   Record last-polled timestamp per feed in Redis

### `dedupe.py`

-   Check if URL already processed using Redis SET (`seen:urls`)
-   TTL: 7 days (articles older than 7 days won't re-process)
-   Also check canonical URL after fetch (redirects can produce
    duplicates)

### `rss_worker.py`

-   Celery beat task that triggers `poller.py` on schedule
-   Separate from `fetch_worker.py` --- RSS polling and fetch/normalize
    are decoupled

---

## 5. Normalizer (`app/fetch/normalizer.py`) --- Already Implemented

### What exists

-   Title, author, publish-time, lead extraction
-   Boilerplate cleaning
-   Language detection (en/hi)
-   spaCy NER (PERSON, ORG, GPE)
-   Gazetteer location normalization
-   Relative date resolution
-   TF-IDF keyword derivation
-   Raw HTML encryption

### What to add when extending

-   Do not remove encryption --- it's required
-   Language detection is naive --- don't build hard dependencies on it
    being accurate for mixed-language articles
-   Any new NLP step must degrade gracefully if the model isn't loaded
    (log warning, skip step, continue)

---

## 6. FastAPI Endpoints

### Structure

    app/
    ├── routers/
    │   ├── clusters.py
    │   ├── summaries.py
    │   ├── outlets.py
    │   └── health.py
    ├── schemas/
    ├── services/
    └── main.py

Endpoints: - `GET /clusters` - `GET /clusters/{id}` -
`GET /summaries/{cluster_id}` - `GET /outlets` - `GET /outlets/{id}` -
`GET /health` - `GET /ready`

### Rules

-   Routers only handle HTTP concerns (request parsing, response
    shaping)
-   Business logic goes in `services/` --- never inline in routers
-   Always use Pydantic response models --- never return raw dicts
-   All endpoints must have explicit `response_model` and `status_code`
-   Health endpoint must check DB + Redis connectivity, not just return
    200

---

## 7. Error Handling Standard

``` python
import logging
log = logging.getLogger(__name__)

try:
    result = await do_thing()
except SpecificError as e:
    log.error("Context: what was being attempted. Error: %s", e, exc_info=True)
    raise
```

### Rules

-   Never use bare `except:` --- always catch specific exceptions
-   Always log with enough context to reproduce: what URL, what outlet,
    what cluster ID
-   Redis errors and DB errors must never silently fail --- they must
    propagate or be explicitly retried
-   `XACK` only after confirmed success --- if in doubt, do not ack

---

## 8. Environment Variables

All config via env vars. Never hardcode:

    DATABASE_URL
    REDIS_URL
    ENCRYPTION_KEY
    EMBEDDING_MODEL
    FRAME_MODEL_PATH
    LOG_LEVEL

Use `pydantic-settings` for typed env config:

``` python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    encryption_key: str
```

---

## 9. Testing Rules

-   Test files go in `/tests`
-   File naming: `test_{module_name}.py`
-   Use `pytest` + `pytest-asyncio` for async tests
-   Mock Redis and DB in unit tests --- never hit real infra in unit
    tests
-   Integration tests (real infra) go in `tests/integration/` and
    require Docker Compose running
-   Every new module must have at least:
    -   one happy-path test
    -   one failure/error test

---

## What Not To Do

-   Never hardcode domain rate limits or similarity thresholds as magic
    numbers --- put them in config
-   Never call the embedding model or frame classifier inside a
    request/response cycle --- these are async pipeline steps only
-   Never store outlet ranking, bias scores, or ideological
    classifications in the DB schema
-   Never `XACK` before the downstream operation completes
-   Never open DB connections outside `app/db.py`
