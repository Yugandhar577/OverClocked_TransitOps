---
name: redis
description: >
  Production Redis patterns for Python async applications: connection pooling, Streams (XADD/
  XREADGROUP), caching, pub/sub, distributed locks, rate limiting, and pipeline/transaction
  patterns using redis-py v5+ async client. Use this skill whenever the user is working with
  Redis in Python — including Redis Streams consumer groups, cache invalidation, Lua scripts,
  key expiry, or async connection management. Trigger for any mention of redis-py, aioredis,
  Redis Streams, XADD, XREADGROUP, Redis cache, Redis pub/sub, or Redis locks.
---

# Redis — Production Skill

## Stack
- Redis 7.x+
- `redis-py` v5+ (`pip install redis[hiredis]`)
- async client via `redis.asyncio`
- `hiredis` for faster parsing (included via `redis[hiredis]`)

> **Note:** `aioredis` is legacy. Since redis-py v4.2, use `redis.asyncio` — same API, actively maintained, no separate package.

---

## Connection pool setup (`app/redis.py`)

```python
from redis.asyncio import Redis, ConnectionPool

_pool: ConnectionPool | None = None
_client: Redis | None = None

async def init_redis(url: str, max_connections: int = 20) -> None:
    global _pool, _client
    _pool = ConnectionPool.from_url(
        url,
        max_connections=max_connections,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    _client = Redis(connection_pool=_pool)
    await _client.ping()

async def close_redis() -> None:
    if _client:
        await _client.aclose()
    if _pool:
        await _pool.aclose()

def get_redis() -> Redis:
    if _client is None:
        raise RuntimeError("Redis not initialized")
    return _client
```

Call `init_redis()` in FastAPI lifespan. Inject via `Depends(get_redis)`.

---

## FastAPI dependency

```python
from fastapi import Depends
from redis.asyncio import Redis
from .redis import get_redis

async def redis_dep() -> Redis:
    return get_redis()
```

One shared pool. Never create a new `Redis()` per request.

---

## Redis Streams — Producer

```python
async def publish_event(
    redis: Redis,
    stream: str,
    event: dict,
    maxlen: int = 10_000,
) -> str:
    msg_id = await redis.xadd(
        stream,
        event,
        maxlen=maxlen,   # MAXLEN ~ keeps stream bounded
        approximate=True,  # MAXLEN ~ (approximate, faster)
    )
    return msg_id
```

`approximate=True` uses `MAXLEN ~` — much faster, keeps stream near `maxlen`. Exact trimming is expensive on large streams.

---

## Redis Streams — Consumer group setup

```python
async def ensure_consumer_group(
    redis: Redis,
    stream: str,
    group: str,
) -> None:
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise
```

`mkstream=True` creates the stream if it doesn't exist. `BUSYGROUP` error means group already exists — safe to ignore.

---

## Redis Streams — Consumer worker

```python
import asyncio
from redis.asyncio import Redis

async def stream_worker(
    redis: Redis,
    stream: str,
    group: str,
    consumer: str,
    batch_size: int = 10,
    block_ms: int = 2000,
) -> None:
    while True:
        try:
            messages = await redis.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},  # ">" = undelivered messages only
                count=batch_size,
                block=block_ms,
            )
            if not messages:
                continue

            for stream_name, entries in messages:
                for msg_id, fields in entries:
                    try:
                        await process_message(fields)
                        await redis.xack(stream, group, msg_id)
                    except Exception as exc:
                        # Leave unacked — will reappear via XPENDING
                        logger.error("Failed to process %s: %s", msg_id, exc)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Worker error: %s", exc)
            await asyncio.sleep(1)
```

**At-least-once delivery:** Message is only removed from PEL (Pending Entry List) after `XACK`. Unacked messages are re-deliverable via `XCLAIM`.

---

## Pending message recovery (dead-letter handling)

```python
async def recover_pending(
    redis: Redis,
    stream: str,
    group: str,
    consumer: str,
    min_idle_ms: int = 60_000,
) -> None:
    pending = await redis.xpending_range(
        stream, group, min="-", max="+", count=100
    )
    for entry in pending:
        if entry["time_since_delivered"] > min_idle_ms:
            await redis.xclaim(
                stream, group, consumer,
                min_idle_time=min_idle_ms,
                message_ids=[entry["message_id"]],
            )
```

Run recovery as a background coroutine on a timer (e.g., every 60s).

---

## Caching patterns

```python
import json
from redis.asyncio import Redis

async def get_cached_or_fetch(
    redis: Redis,
    key: str,
    fetch_fn,
    ttl: int = 300,
):
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    value = await fetch_fn()
    await redis.setex(key, ttl, json.dumps(value, default=str))
    return value

# Cache invalidation
async def invalidate(redis: Redis, key: str) -> None:
    await redis.delete(key)

# Pattern invalidation (use carefully — O(N) scan)
async def invalidate_prefix(redis: Redis, prefix: str) -> None:
    async for key in redis.scan_iter(match=f"{prefix}:*", count=100):
        await redis.delete(key)
```

---

## Pipeline (batching commands)

```python
async def bulk_set(redis: Redis, items: dict[str, str], ttl: int) -> None:
    async with redis.pipeline(transaction=False) as pipe:
        for key, value in items.items():
            pipe.setex(key, ttl, value)
        await pipe.execute()
```

`transaction=False` = no MULTI/EXEC, faster for non-atomic batches. Use `transaction=True` when atomicity is needed.

---

## Distributed lock

```python
import uuid
from redis.asyncio import Redis

class RedisLock:
    def __init__(self, redis: Redis, key: str, ttl: int = 30):
        self.redis = redis
        self.key = f"lock:{key}"
        self.ttl = ttl
        self.token = str(uuid.uuid4())

    async def acquire(self) -> bool:
        return await self.redis.set(
            self.key, self.token, nx=True, ex=self.ttl
        ) is not None

    async def release(self) -> None:
        # Lua script for atomic check-and-delete
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        await self.redis.eval(script, 1, self.key, self.token)

    async def __aenter__(self):
        if not await self.acquire():
            raise RuntimeError(f"Could not acquire lock: {self.key}")
        return self

    async def __aexit__(self, *_):
        await self.release()
```

---

## Rate limiting (token bucket via Lua)

```python
RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call('incr', key)
if current == 1 then
    redis.call('expire', key, window)
end
return current
"""

async def check_rate_limit(
    redis: Redis,
    identifier: str,
    limit: int = 100,
    window_sec: int = 60,
) -> bool:
    key = f"ratelimit:{identifier}"
    current = await redis.eval(RATE_LIMIT_SCRIPT, 1, key, limit, window_sec)
    return int(current) <= limit
```

---

## Key naming conventions

```
{service}:{entity}:{id}          # e.g., api:article:123
{service}:{entity}:{id}:lock     # distributed lock
stream:{service}:{event_type}    # e.g., stream:fetch:articles
ratelimit:{ip_or_user_id}
session:{session_token}
```

Always namespace keys. Avoids collisions in shared Redis instances.

---

## Common pitfalls

- ❌ `decode_responses=False` (default) — you'll get bytes everywhere; always set `True` for string data
- ❌ Creating a new `Redis()` per request — use the shared pool
- ❌ `redis.xreadgroup(..., streams={stream: "0"})` — `"0"` re-reads ALL pending, not new messages; use `">"` for new
- ❌ Not calling `XACK` after processing — messages pile up in PEL, memory leak
- ❌ Exact `MAXLEN` on XADD hot path — use approximate (`~`)
- ❌ Using `KEYS` command in production — O(N) blocks Redis; use `SCAN`
- ❌ Storing large blobs (>10KB) in Redis — use object storage + store only reference key
- ❌ Not handling `ConnectionError` / `TimeoutError` in consumers — always wrap with try/except + backoff
