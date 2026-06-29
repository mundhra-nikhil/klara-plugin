"""Celery app configuration (broker=Redis)."""

from celery import Celery
from kombu import Queue

app = Celery('grss', broker='redis://redis:6379/0', backend='redis://redis:6379/1')

app.conf.update(
    task_queues=[
        Queue('high',    routing_key='high.#'),
        Queue('default', routing_key='default.#'),
        Queue('low',     routing_key='low.#'),
    ],
    task_default_queue='default',
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
    task_retry_backoff=True,
    task_retry_backoff_max=60,
    worker_concurrency=10,
    worker_prefetch_multiplier=1,
    task_rate_limit='10/s',
    result_expires=3600,
)
