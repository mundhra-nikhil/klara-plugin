"""Real-Redis + retry-path integration tests for the hardened AI job pipeline.

These exercise what the unit suite (``test_ai_jobs``) stubs out:

  * ``src.utils.doc_lock`` against a **live** redis — CAS release, a concurrent
    waiter that unblocks on release, wrong-token release is a no-op, TTL
    auto-expiry lets a new owner in, and ``compute_backoff`` stays in bounds.
  * the ``process_ai_job`` retry / terminal-failure state machine — a transient
    failure lands the job in ``RETRYING`` with an audit log + ``retry_count``,
    then succeeds; a permanent failure reaches ``FAILED`` after exactly
    ``AI_JOB_MAX_RETRIES + 1`` attempts and never requeues again.

The lock tests bind the **real** functions at import time, so conftest's autouse
``_stub_doc_lock`` fixture (which swaps the module attribute) does not divert
them. The retry tests call ``process_ai_job`` directly — the lock lives in the
runner, not the worker — so they need no redis.
"""

import asyncio
import uuid

import pytest
import redis.asyncio as aioredis
from sqlalchemy import select

from src.core.constants import AI_JOB_MAX_RETRIES, AI_JOB_RETRY_BACKOFF_MAX
from src.models.dao.ai_analysis_job import AIAnalysisJob
from src.models.dao.audit_log import AuditLog
from src.models.dao.client import Client
from src.models.dao.document import Document
from src.models.enum.document_status import DocumentStatus
from src.models.enum.document_type import DocumentType
from src.models.enum.job_status import AIJobStatus, AuditAction
from src.models.enum.job_type import AIJobType
from src.repositories.db_setup import AsyncSessionLocal
from src.services.ai_jobs import ai_job_service, rule_engine
from src.utils.doc_lock import acquire_doc_lock as _real_acquire
from src.utils.doc_lock import compute_backoff
from src.utils.doc_lock import release_doc_lock as _real_release


async def _require_redis() -> None:
    """Skip the calling test if there is no live redis on localhost:6379."""
    try:
        r = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
        await r.ping()
        await r.aclose()
    except OSError:
        pytest.skip("no live redis on localhost:6379")


# --------------------------------------------------------------------------- #
# Real-redis lock behavior
# --------------------------------------------------------------------------- #

async def test_lock_acquire_release_reacquire():
    await _require_redis()
    doc_id = uuid.uuid4()
    lock = await _real_acquire(doc_id, ttl=10, wait_timeout=1)
    assert lock is not None
    key, token = lock
    assert await _real_release(key, token) is True
    # Re-acquiring immediately after a valid release must succeed.
    lock2 = await _real_acquire(doc_id, ttl=10, wait_timeout=1)
    assert lock2 is not None
    await _real_release(*lock2)


async def test_lock_wrong_token_is_noop():
    await _require_redis()
    doc_id = uuid.uuid4()
    key, token = await _real_acquire(doc_id, ttl=10, wait_timeout=1)
    # A bogus token must NOT release the lock (CAS guard).
    assert await _real_release(key, "bogus-token") is False
    # A second acquirer must still time out — the lock is held.
    assert await _real_acquire(doc_id, ttl=10, wait_timeout=1) is None
    await _real_release(key, token)


async def test_lock_concurrent_waiter_acquires_after_release():
    await _require_redis()
    doc_id = uuid.uuid4()
    key, token = await _real_acquire(doc_id, ttl=10, wait_timeout=1)

    async def waiter():
        return await _real_acquire(doc_id, ttl=10, wait_timeout=5)

    wait_task = asyncio.create_task(waiter())
    await asyncio.sleep(0.4)                  # let the waiter start polling
    assert not wait_task.done(), "waiter must stay blocked while the lock is held"
    await _real_release(key, token)           # free it
    lock2 = await asyncio.wait_for(wait_task, timeout=5)
    assert lock2 is not None, "waiter must acquire once the lock is released"
    await _real_release(*lock2)


async def test_lock_ttl_auto_expiry_lets_others_in():
    await _require_redis()
    doc_id = uuid.uuid4()
    await _real_acquire(doc_id, ttl=2, wait_timeout=1)   # held, never released
    await asyncio.sleep(2.4)                             # let the TTL expire
    # A new acquirer gets in despite no explicit release.
    lock2 = await _real_acquire(doc_id, ttl=5, wait_timeout=1)
    assert lock2 is not None
    await _real_release(*lock2)


def test_compute_backoff_within_bounds():
    for n in range(1, AI_JOB_MAX_RETRIES + 3):
        d = compute_backoff(n)
        assert 0.0 <= d <= AI_JOB_RETRY_BACKOFF_MAX, (n, d)
    # Caps at the max even for absurd retry counts.
    assert compute_backoff(50) <= AI_JOB_RETRY_BACKOFF_MAX


# --------------------------------------------------------------------------- #
# Retry / terminal-failure state machine (process_ai_job, driven directly)
# --------------------------------------------------------------------------- #

async def _seed_document() -> uuid.UUID:
    """Insert a Client + Document directly (validation_mode='review_assist' so
    no auto Klara run is triggered)."""
    async with AsyncSessionLocal() as db:
        client = Client(
            name=f"resilience-test-{uuid.uuid4().hex[:8]}",
            code=f"RT{uuid.uuid4().hex[:6]}",
            blob_container_name="resilience-test",
            is_active=True,
        )
        db.add(client)
        await db.flush()
        doc = Document(
            client_id=client.id,
            title="Resilience Test Doc",
            document_type=DocumentType.FORMATTING,
            status=DocumentStatus.RECEIVED,
            blob_url="local://resilience-test",
            blob_container="resilience-test",
            metadata_={},
            validation_mode="review_assist",
        )
        db.add(doc)
        await db.commit()
        return doc.id


async def _make_pending_job(document_id) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        job = AIAnalysisJob(
            document_id=document_id,
            job_type=AIJobType.FORMATTING_CHECK,
            status=AIJobStatus.PENDING,
        )
        db.add(job)
        await db.commit()
        return job.id


async def _reload(job_id) -> AIAnalysisJob:
    async with AsyncSessionLocal() as db:
        return await db.get(AIAnalysisJob, job_id)


async def test_retry_once_then_completes(monkeypatch):
    document_id = await _seed_document()
    job_id = await _make_pending_job(document_id)

    real_analyze = rule_engine.analyze
    calls = {"n": 0}

    def flaky_analyze(*args, **kwargs):
        if calls["n"] == 0:
            calls["n"] += 1
            raise RuntimeError("transient boom")
        return real_analyze(*args, **kwargs)

    monkeypatch.setattr(rule_engine, "analyze", flaky_analyze)

    # Attempt 1: rule engine raises → RETRYING with retry_count=1.
    async with AsyncSessionLocal() as db:
        status1 = await ai_job_service.process_ai_job(db, job_id)
        await db.commit()
    assert status1 == AIJobStatus.RETRYING
    j = await _reload(job_id)
    assert j.retry_count == 1
    assert "transient boom" in (j.error_message or "")

    # Attempt 2 (job now RETRYING → admitted by the guard): succeeds → COMPLETED.
    async with AsyncSessionLocal() as db:
        status2 = await ai_job_service.process_ai_job(db, job_id)
        await db.commit()
    assert status2 == AIJobStatus.COMPLETED
    j = await _reload(job_id)
    assert j.retry_count == 1            # success does not bump retry_count
    assert j.status == AIJobStatus.COMPLETED

    # An audit-log STATUS_CHANGE entry records the RETRYING transition.
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(AuditLog).where(
                AuditLog.entity_id == job_id,
                AuditLog.action == AuditAction.STATUS_CHANGE,
            )
        )).scalars().all()
    assert any((r.new_values or {}).get("status") == "retrying" for r in rows)


def _always_raise(*args, **kwargs):
    raise RuntimeError("permanent boom")


async def test_terminal_failure_after_max_retries(monkeypatch):
    document_id = await _seed_document()
    job_id = await _make_pending_job(document_id)
    monkeypatch.setattr(rule_engine, "analyze", _always_raise)

    # Drive AI_JOB_MAX_RETRIES + 1 attempts (1 initial + N retries): each RETRYING
    # until the cap, then FAILED on the final one.
    last_status = None
    for _ in range(AI_JOB_MAX_RETRIES + 1):
        async with AsyncSessionLocal() as db:
            last_status = await ai_job_service.process_ai_job(db, job_id)
            await db.commit()
    assert last_status == AIJobStatus.FAILED
    j = await _reload(job_id)
    assert j.retry_count == AI_JOB_MAX_RETRIES + 1

    # A further call must be a no-op (FAILED isn't runnable) — proves no
    # unbounded requeue: retry_count does not grow past the cap.
    async with AsyncSessionLocal() as db:
        await ai_job_service.process_ai_job(db, job_id)
        await db.commit()
    j = await _reload(job_id)
    assert j.status == AIJobStatus.FAILED
    assert j.retry_count == AI_JOB_MAX_RETRIES + 1
