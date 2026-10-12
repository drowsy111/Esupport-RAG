from app.core.config import get_settings
from app.db.session import create_session_factory
from app.services.ingestion_service import run_ingestion
from app.services.resources import Resources
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.ingest_document")
def ingest_document(job_id: str):
    settings = get_settings()
    engine, factory = create_session_factory(settings.database_url)
    resources = Resources.production(settings)
    try:
        run_ingestion(job_id, factory, resources, settings)
    finally:
        resources.close()
        engine.dispose()

