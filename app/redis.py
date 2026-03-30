import json
import redis.asyncio as aioredis
from typing import Any, Optional
from app.config import settings


# Global Redis client
redis_client: aioredis.Redis = None


async def init_redis():
    """Initialize Redis connection on startup"""
    global redis_client
    redis_client = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,     # handle many concurrent players
    )
    return redis_client


async def close_redis():
    """Close Redis connection on shutdown"""
    global redis_client
    if redis_client:
        await redis_client.close()


def get_redis() -> aioredis.Redis:
    """Dependency — use this in FastAPI routes"""
    return redis_client


# ── Key builders ────────────────────────────────────────────
# Keeps key naming consistent across the entire codebase

def key_token(token: str) -> str:
    return f"token:{token}"

def key_venue(venue_id: int) -> str:
    return f"venue:{venue_id}"

def key_session(session_id: int) -> str:
    return f"session:{session_id}"

def key_table(venue_id: int, table_number: int) -> str:
    return f"table:{venue_id}:{table_number}"

def key_lobby(lobby_id: int) -> str:
    return f"lobby:{lobby_id}"

def key_game_state(lobby_id: int) -> str:
    return f"game_state:{lobby_id}"

def key_round(round_id: int) -> str:
    return f"round:{round_id}"

def key_answer(round_id: int, player_id: int) -> str:
    return f"answer:{round_id}:{player_id}"

def key_rate_limit(token: str, action: str) -> str:
    return f"rate:{token}:{action}"

def key_mutex(resource: str) -> str:
    return f"mutex:{resource}"


# ── Helper functions ─────────────────────────────────────────

async def set_json(key: str, data: Any, expire: int = None):
    """Store a dict/list as JSON in Redis"""
    value = json.dumps(data)
    if expire:
        await redis_client.setex(key, expire, value)
    else:
        await redis_client.set(key, value)


async def get_json(key: str) -> Optional[Any]:
    """Retrieve and parse JSON from Redis"""
    value = await redis_client.get(key)
    if value:
        return json.loads(value)
    return None


async def acquire_mutex(resource: str, expire: int = 5) -> bool:
    """
    Try to acquire a mutex lock for a resource.
    Returns True if lock acquired, False if already locked.
    Used to prevent race conditions on answer submission.
    """
    key = key_mutex(resource)
    result = await redis_client.set(key, "locked", nx=True, ex=expire)
    return result is not None


async def release_mutex(resource: str):
    """Release a mutex lock"""
    key = key_mutex(resource)
    await redis_client.delete(key)


async def check_rate_limit(token: str, action: str, limit: int, window: int) -> bool:
    """
    Check if a token has exceeded rate limit for an action.
    Returns True if allowed, False if rate limited.
    limit  → max number of actions
    window → time window in seconds
    """
    key = key_rate_limit(token, action)
    count = await redis_client.get(key)

    if count is None:
        # First action — set counter with expiry
        await redis_client.setex(key, window, 1)
        return True

    if int(count) >= limit:
        return False

    await redis_client.incr(key)
    return True