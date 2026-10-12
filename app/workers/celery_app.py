from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "enterprise_support_rag", broker=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], result_serializer="json",
    task_ignore_result=True, task_acks_late=True, worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 7200},
    task_routes={"app.workers.tasks.ingest_document": {"queue": "ingestion"}},
)

