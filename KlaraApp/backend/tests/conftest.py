"""Pytest fixtures, async DB setup, and test client configuration."""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()



@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _stub_doc_lock(monkeypatch):
    """AI jobs serialize via a Redis lock (``src.utils.doc_lock``). The test
    suite has no live Redis — ``ASGITransport`` never runs the app lifespan, so
    ``redis_client`` is never connected — so replace the lock with a
    process-local ``asyncio.Lock`` per document. This both avoids
    ``ConnectionError`` in background tasks and serializes the 6 same-document
    jobs ``test_create_ai_job_all_roles`` submits, preventing DB contention."""
    import src.utils.doc_lock as doc_lock

    _locks: dict[str, asyncio.Lock] = {}

    async def _acquire(document_id, **kwargs):
        key = f"test-lock:{document_id}"
        lock = _locks.setdefault(key, asyncio.Lock())
        await lock.acquire()
        return (key, "test-token")

    async def _release(key, token):
        lock = _locks.get(key)
        if lock is not None:
            try:
                lock.release()
            except RuntimeError:
                pass  # already released
        return True

    monkeypatch.setattr(doc_lock, "acquire_doc_lock", _acquire)
    monkeypatch.setattr(doc_lock, "release_doc_lock", _release)


@pytest_asyncio.fixture(autouse=True)
async def _drain_inflight_ai_jobs():
    """Cancel and await any background AI-job tasks spawned during a test (the
    initial run plus any retry chain) so they don't leak across the
    pytest-asyncio event loop and raise 'Task was destroyed but it is pending!'."""
    yield
    from src.services.ai_jobs import ai_job_service
    tasks = set(ai_job_service._INFLIGHT_BG_TASKS)
    for t in tasks:
        t.cancel()
    for t in tasks:
        try:
            await t
        except (Exception, asyncio.CancelledError):
            pass
