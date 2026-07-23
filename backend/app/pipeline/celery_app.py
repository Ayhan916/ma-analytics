from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "ma_analytics",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.pipeline.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,

    # Task timeout: warn at 25 min, kill at 30 min
    task_soft_time_limit=1500,
    task_time_limit=1800,

    # Retry on worker restart
    task_acks_late=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,

    # Result expiry (keep results 24h)
    result_expires=86400,
)
