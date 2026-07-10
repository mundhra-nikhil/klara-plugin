"""Per-document Redis lock for serializing AI analysis jobs.

A job acquires ``doc_lock:{document_id}`` before touching a document's findings,
so two concurrent jobs on the same document can't interleave delete/insert and
clobber each other's results.

The functions here are module-level (not methods) deliberately, so the test
suite can monkeypatch ``acquire_doc_lock`` / ``release_doc_lock`` without a live
Redis (the suite's ``ASGITransport`` client never starts the app lifespan, so
``redis_client`` is never connected).
"""

import asyncio
import random
import time
import uuid

from redis.exceptions import RedisError

from src.core.constants import AI_JOB_RETRY_BACKOFF_MAX
from src.core.logger import get_logger_with_context
from src.core.state import redis_client

logger = get_logger_with_context()

# Compare-and-delete: only remove the key if it still holds OUR token. Prevents
# a stale owner from deleting a lock a new owner legitimately acquired after the
# TTL expired.
_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""
_release_script = redis_client.register_script(_RELEASE_SCRIPT)


def _key(document_id) -> str:
    return f"doc_lock:{document_id}"


async def acquire_doc_lock(
    document_id,
    *,
    ttl: int = 600,
    wait_timeout: float = 480,
    poll_interval: float = 0.25,
) -> tuple[str, str] | None:
    """Block until we hold the per-document lock, or give up.

    Returns ``(key, token)`` on success, or ``None`` if the lock couldn't be
    acquired within ``wait_timeout``. ``wait_timeout`` is kept below ``ttl`` so a
    waiter gives up before a held lock could expire and become stealable by
    someone else. The poll uses ``await asyncio.sleep`` so it never blocks the
    event loop (and so the lock holder — another task in the same loop — can
    progress and release).
    """
    key = _key(document_id)
    token = uuid.uuid4().hex
    deadline = time.monotonic() + wait_timeout
    while True:
        if await redis_client.set(key, token, nx=True, ex=ttl):
            return key, token
        if time.monotonic() >= deadline:
            return None
        await asyncio.sleep(poll_interval)


async def release_doc_lock(key: str, token: str) -> bool:
    """Release the lock only if we still own it. Never raises (safe in finally)."""
    try:
        return bool(await _release_script(keys=[key], args=[token]))
    except RedisError as e:
        logger.warning(f"Failed to release doc lock {key}: {e}")
        return False


def compute_backoff(retry_count: int) -> float:
    """Full-jitter exponential backoff (seconds) for a retry attempt.

    Caps the base at ``AI_JOB_RETRY_BACKOFF_MAX``; full jitter spreads
    simultaneous failures so they don't all retry in lockstep after a shared
    outage (DB/Redis blip).
    """
    base = min(AI_JOB_RETRY_BACKOFF_MAX, 5 * (2 ** (retry_count - 1)))
    return random.uniform(0, base)
