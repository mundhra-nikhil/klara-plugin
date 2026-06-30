"""Global application state, caches, and startup initialization."""

import redis.asyncio as redis
from src.configs.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def get_redis():
    return redis_client


async def init_state():
    """Initialize global state on application startup."""
    await redis_client.ping()


async def cleanup_state():
    """Cleanup global state on application shutdown."""
    await redis_client.close()
