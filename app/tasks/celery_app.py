from celery import Celery
from app.config import settings

celery_app = Celery(
    "webhook_service",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=False,
    # Prevent workers from reserving a backlog of 30-second tasks ahead of other workers.
    worker_prefetch_multiplier=1,
    # The API does not read AsyncResult values, so avoid writing task results to Postgres.
    task_ignore_result=True,
    task_time_limit=30 * 60,
)