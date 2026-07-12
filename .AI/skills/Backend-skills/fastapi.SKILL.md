---
name: fastapi
description: >
  Production-grade FastAPI patterns for async Python APIs. Use this skill whenever the user is
  building, debugging, or architecting a FastAPI application — including routing, dependency
  injection, middleware, lifespan management, Pydantic schemas, error handling, background tasks,
  testing, or deployment. Trigger even for partial FastAPI questions (e.g., "how do I structure
  my router", "how do I handle auth in FastAPI", "why is my async endpoint slow").
---

# FastAPI — Production Skill

## Stack assumptions
- Python 3.12+
- FastAPI 0.115+
- Pydantic v2
- `asyncpg` or `SQLAlchemy 2.x` async for DB
- `uvicorn` (dev) / `gunicorn + uvicorn workers` (prod)
- `pydantic-settings` for config

---

## Project structure (domain-first, not file-type-first)

```
src/
├── main.py               # app factory, lifespan, middleware
├── config.py             # Settings via pydantic-settings
├── deps.py               # Shared FastAPI dependencies
├── db.py                 # Engine + session factory
├── redis.py              # Redis pool factory
├── <domain>/
│   ├── router.py         # APIRouter
│   ├── schemas.py        # Pydantic request/response models
│   ├── models.py         # SQLAlchemy ORM models
│   ├── service.py        # Business logic (no HTTP concerns)
│   └── repository.py     # DB queries only
alembic/
tests/
```

**Rule:** Routers are thin. Services hold logic. Repositories hold queries.

---

## App factory + lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .db import init_db, close_db
from .redis import init_redis, close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    yield
    await close_db()
    await close_redis()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="My API")
    app.include_router(articles.router, prefix="/articles", tags=["articles"])
    return app
```

Never use `@app.on_event("startup")` — deprecated. Always use `lifespan`.

---

## Config with pydantic-settings

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    redis_url: str
    secret_key: str
    debug: bool = False

from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## Dependency injection patterns

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .db import async_session_factory
from .config import get_settings, Settings

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    ...
```

**Rules:**
- Use `async def` deps for I/O, plain `def` only for CPU-only ops (no threadpool waste).
- Chain deps: `get_current_admin` depends on `get_current_user`.
- Deps are cached per-request scope by default — rely on this.

---

## Router + schema patterns

```python
# router.py
router = APIRouter()

@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = await article_service.get(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
```

```python
# schemas.py — Pydantic v2
from pydantic import BaseModel, ConfigDict

class ArticleBase(BaseModel):
    title: str
    content: str

class ArticleCreate(ArticleBase):
    pass

class ArticleOut(ArticleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
```

---

## Error handling

```python
# main.py
from fastapi import Request
from fastapi.responses import JSONResponse

class AppError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
```

Never raise raw `Exception` inside route handlers. Always raise `HTTPException` or a typed `AppError`.

---

## Async rules — critical

| Pattern | Correct |
|---|---|
| `async def route` + `await db.execute(...)` | ✅ |
| `async def route` + `requests.get(...)` (blocking) | ❌ deadlocks event loop |
| `def route` + blocking I/O | ✅ runs in threadpool |
| `async def dep` doing pure CPU work | ❌ use plain `def` |

For blocking SDKs that can't be made async, wrap in `asyncio.to_thread`:
```python
result = await asyncio.to_thread(blocking_sdk_call, arg)
```

---

## Background tasks

```python
from fastapi import BackgroundTasks

@router.post("/articles")
async def create_article(
    payload: ArticleCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    article = await article_service.create(db, payload)
    background_tasks.add_task(notify_subscribers, article.id)
    return article
```

For heavy/long-running work, use a proper task queue (Celery, ARQ, Redis Streams) instead of `BackgroundTasks`.

---

## Middleware

```python
from fastapi.middleware.cors import CORSMiddleware
import time, uuid

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(time.perf_counter() - start)
    return response
```

---

## Health check endpoint

```python
@app.get("/health", tags=["ops"])
async def health(db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    await db.execute(text("SELECT 1"))
    await redis.ping()
    return {"status": "ok"}
```

Always check real dependencies in `/health` — liveness vs readiness matters for k8s.

---

## Testing

```python
# conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import create_app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as ac:
        yield ac
```

Use `httpx.AsyncClient` + `ASGITransport` — not `TestClient` for async routes.

---

## Production deployment

```
# gunicorn with uvicorn workers
gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 4 \
  --bind 0.0.0.0:8000 \
  --timeout 60 \
  --graceful-timeout 30
```

Worker count: `(2 × CPU_cores) + 1` is for sync workers. For async uvicorn workers, match CPU count or slightly above, then scale horizontally.

---

## Anti-patterns checklist

- ❌ `from app.db import engine` at module level (import-time side effects)
- ❌ `Session()` without context manager (leaked connections)
- ❌ Calling `requests.get()` inside `async def` (blocks event loop)
- ❌ Returning raw ORM model without response_model (leaks data)
- ❌ Business logic in router functions
- ❌ `@app.on_event` (deprecated)
- ❌ `global` state for connection objects (use `app.state` or deps)
