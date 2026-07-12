---
name: postgres-pgvector
description: >
  Production PostgreSQL with pgvector using SQLAlchemy 2.x async + asyncpg. Use this skill
  whenever the user is working with PostgreSQL in Python — including async sessions, connection
  pooling, ORM models, Alembic migrations, vector similarity search, HNSW/IVFFlat indexes,
  hybrid search, or performance tuning of vector queries. Trigger for any mention of pgvector,
  vector search, embeddings in Postgres, asyncpg, SQLAlchemy async, or Alembic.
---

# PostgreSQL + pgvector — Production Skill

## Stack
- PostgreSQL 16+
- pgvector 0.7+ (extension)
- SQLAlchemy 2.x (async, declarative)
- asyncpg (driver)
- Alembic (migrations)
- pgvector-python (`pip install pgvector`)

---

## Engine + session factory (`app/db.py`)

```python
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host:5432/dbname",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,       # drop stale connections
    pool_recycle=3600,        # recycle connections after 1h
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,   # critical: avoid lazy-load after commit
    class_=AsyncSession,
)

class Base(DeclarativeBase):
    pass

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    await engine.dispose()
```

**`expire_on_commit=False` is mandatory** in async contexts — otherwise accessing attributes after commit triggers a lazy-load that fails outside a session.

---

## ORM model with vector column

```python
from sqlalchemy import Column, Integer, String, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from datetime import datetime
from .db import Base

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

# Index defined outside class — must be created via migration
hnsw_index = Index(
    "articles_embedding_hnsw_idx",
    Article.embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
```

---

## Index choice: HNSW vs IVFFlat

| | HNSW | IVFFlat |
|---|---|---|
| Build time | Slower | Faster |
| Query speed | Faster (no training) | Depends on `lists` |
| Recall | Higher | Lower |
| Best for | Production (<10M vectors) | Large batch inserts first |
| Operator classes | `vector_cosine_ops`, `vector_l2_ops`, `vector_ip_ops` | same |

**Default choice: HNSW** for most production workloads. Tune `ef_search` at query time:

```sql
SET hnsw.ef_search = 100;
```

IVFFlat: set `lists ≈ sqrt(row_count)`. Must rebuild index after large bulk loads.

---

## Distance operators

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import func, select

# Cosine distance (most common for text embeddings, normalized vectors)
stmt = (
    select(Article)
    .order_by(Article.embedding.cosine_distance(query_embedding))
    .limit(10)
)

# L2 distance
.order_by(Article.embedding.l2_distance(query_embedding))

# Inner product (negative; use for max_inner_product)
.order_by(Article.embedding.max_inner_product(query_embedding))
```

Use **cosine** for sentence-transformer embeddings (unit-normalized). Use **L2** for raw feature vectors.

---

## Repository pattern — async

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import Article

class ArticleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, article_id: int) -> Article | None:
        return await self.session.get(Article, article_id)

    async def vector_search(
        self,
        embedding: list[float],
        limit: int = 10,
        threshold: float = 0.3,
    ) -> list[tuple[Article, float]]:
        dist = Article.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(Article, dist)
            .where(Article.embedding.cosine_distance(embedding) < threshold)
            .order_by(dist)
            .limit(limit)
        )
        rows = await self.session.execute(stmt)
        return rows.all()

    async def upsert(self, article: Article) -> Article:
        self.session.add(article)
        await self.session.flush()  # get ID before commit if needed
        return article
```

---

## FastAPI session dependency

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .db import async_session_factory

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        async with session.begin():   # auto-commit / auto-rollback
            yield session
```

`session.begin()` as context manager: commits on clean exit, rolls back on exception.

---

## Alembic async setup

`alembic/env.py`:
```python
from sqlalchemy.ext.asyncio import create_async_engine
from app.db import Base

def run_migrations_online():
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))

    async def do_run():
        async with connectable.connect() as connection:
            await connection.run_sync(context.configure, ...)
            async with context.begin_transaction():
                await connection.run_sync(context.run_migrations)

    asyncio.run(do_run())
```

For vector column in migration:
```python
# alembic/versions/xxxx_add_embedding.py
from pgvector.sqlalchemy import Vector

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("articles", sa.Column("embedding", Vector(768), nullable=True))
    op.execute("""
        CREATE INDEX articles_embedding_hnsw_idx ON articles
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
```

Always `CREATE EXTENSION IF NOT EXISTS vector` before creating vector columns.

---

## Hybrid search (vector + keyword)

```python
from sqlalchemy import func, text

async def hybrid_search(
    session: AsyncSession,
    query_text: str,
    query_embedding: list[float],
    limit: int = 10,
) -> list[Article]:
    stmt = text("""
        SELECT id,
               ts_rank(to_tsvector('english', content), plainto_tsquery(:query)) AS text_score,
               1 - (embedding <=> :embedding) AS vector_score
        FROM articles
        WHERE to_tsvector('english', content) @@ plainto_tsquery(:query)
           OR embedding <=> :embedding < 0.4
        ORDER BY (
            0.5 * ts_rank(to_tsvector('english', content), plainto_tsquery(:query)) +
            0.5 * (1 - (embedding <=> :embedding))
        ) DESC
        LIMIT :limit
    """)
    result = await session.execute(
        stmt,
        {"query": query_text, "embedding": str(query_embedding), "limit": limit},
    )
    return result.fetchall()
```

Add `GIN` index for full-text: `CREATE INDEX ON articles USING gin(to_tsvector('english', content))`.

---

## Connection pool sizing

```
pool_size = (CPU_cores × 2) capped at ~10 per service instance
max_overflow = pool_size × 2
```

PostgreSQL max connections default is 100. Account for all service instances + migrations + monitoring. Set `max_connections` in `postgresql.conf` and use PgBouncer in transaction mode for 100+ concurrent app connections.

---

## Common pitfalls

- ❌ `expire_on_commit=True` (default) in async sessions → `MissingGreenlet` errors
- ❌ Importing ORM models without registering them on `Base.metadata` (tables not created)
- ❌ Using `session.execute(select(...))` then accessing `.scalars()` on wrong type
- ❌ Forgetting `await conn.run_sync(Base.metadata.create_all)` uses sync `create_all`
- ❌ Creating HNSW index before data is loaded → slow index on small dataset (minor for HNSW, critical for IVFFlat)
- ❌ Comparing vectors from different embedding models (768-dim vs 384-dim will hard-error; semantically wrong if from different models)
- ❌ Not casting Python list to numpy/list explicitly — `pgvector` handles `list[float]` natively but some drivers need `np.array`
