import secrets
import hashlib
from datetime import datetime, timedelta
from app.config import settings
from app.redis import redis_client, token_key, set_json, get_json
from typing import Optional


def generate_token() -> str:
    """
    Generate a secure random session token
    Uses 32 bytes of randomness — cryptographically secure
    """
    return secrets.token_urlsafe(32)


async def create_session_token(player_data: dict) -> str:
    """
    Create a token and store player data in Redis
    Returns the token string
    """
    token = generate_token()
    expire_seconds = settings.session_token_expire_hours * 3600

    await set_json(
        token_key(token),
        {
            **player_data,
            "token": token,
            "created_at": datetime.utcnow().isoformat(),
        },
        expire_seconds=expire_seconds,
    )
    return token


async def validate_token(token: str) -> Optional[dict]:
    """
    Validate a token and return player data if valid
    Returns None if token is invalid or expired
    """
    if not token:
        return None

    data = await get_json(token_key(token))
    return data


async def refresh_token(token: str) -> bool:
    """
    Refresh token expiry — call on every player activity
    Keeps active players from being logged out mid game
    """
    key = token_key(token)
    expire_seconds = settings.session_token_expire_hours * 3600
    result = await redis_client.expire(key, expire_seconds)
    return result == 1


async def invalidate_token(token: str) -> bool:
    """
    Invalidate a token immediately
    Used when player is kicked or session ends
    """
    result = await redis_client.delete(token_key(token))
    return result == 1


def hash_contact(contact: str) -> str:
    """
    Hash phone/email for privacy before storing
    We store the hash not the raw contact for matching returning players
    """
    return hashlib.sha256(contact.lower().strip().encode()).hexdigest()