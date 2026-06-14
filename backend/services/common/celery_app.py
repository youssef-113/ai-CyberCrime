"""
Shared Celery application — used by all ACEB microservices.

Broker:  Redis DB 1  (CELERY_BROKER_URL)
Backend: Redis DB 2  (CELERY_RESULT_BACKEND)

Queues
──────
  ocr         → services.ocr.tasks.*
  rag         → services.rag.tasks.*
  classifier  → services.classifier.tasks.*
  default     → services.api.tasks.*
"""
import os
from celery import Celery

CELERY_BROKER_URL    = os.getenv("CELERY_BROKER_URL",    "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

celery_app = Celery(
    "aceb",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "services.api.tasks",
        "services.ocr.tasks",
        "services.rag.tasks",
        "services.classifier.tasks",
    ],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="Africa/Cairo",
    enable_utc=True,
    # Tracking
    task_track_started=True,
    # Limits
    task_time_limit=30 * 60,        # hard kill at 30 min
    task_soft_time_limit=25 * 60,   # soft SIGTERM at 25 min
    # Worker behaviour
    worker_prefetch_multiplier=1,   # one task at a time per worker slot
    worker_max_tasks_per_child=500, # recycle after 500 tasks
    # Result expiry
    result_expires=60 * 60 * 24,    # keep results 24 h
    # Retry store
    task_store_errors_even_if_ignored=True,
    # Acks after execution (safer for OCR — avoids losing jobs on crash)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ── Routing ───────────────────────────────────────────────────────────────────
celery_app.conf.task_routes = {
    "services.ocr.tasks.process_image_async":  {"queue": "ocr"},
    "services.ocr.tasks.process_pdf_async":    {"queue": "ocr"},
    "services.ocr.tasks.process_batch_async":  {"queue": "ocr"},
    "services.rag.tasks.*":                    {"queue": "rag"},
    "services.classifier.tasks.*":             {"queue": "classifier"},
    "services.api.tasks.*":                    {"queue": "default"},
}

# ── Queue declarations (so workers can auto-create if needed) ─────────────────
from kombu import Queue  # noqa: E402

celery_app.conf.task_queues = (
    Queue("ocr"),
    Queue("rag"),
    Queue("classifier"),
    Queue("default"),
)
celery_app.conf.task_default_queue = "default"
