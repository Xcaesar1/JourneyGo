"""Celery application configured for idempotent, late-acknowledged work."""

from __future__ import annotations

import os

from celery import Celery

from ..services.task_events import redis_url

broker_url = os.getenv("CELERY_BROKER_URL", redis_url())
visibility_timeout = int(os.getenv("CELERY_VISIBILITY_TIMEOUT", "720"))

celery_app = Celery(
    "journeyops",
    broker=broker_url,
    include=["backend.app.workers.trip_tasks"],
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": visibility_timeout},
    task_soft_time_limit=int(os.getenv("TRIP_TASK_SOFT_TIME_LIMIT", "600")),
    task_time_limit=int(os.getenv("TRIP_TASK_HARD_TIME_LIMIT", "660")),
    timezone="UTC",
    enable_utc=True,
)
