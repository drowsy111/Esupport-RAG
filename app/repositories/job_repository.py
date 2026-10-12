from sqlalchemy import select

from app.core.exceptions import AppError
from app.db.models import Document, DocumentVersion, IngestionJob
from app.security.permissions import require_kb


def get_job(session, principal, job_id):
    row = session.execute(
        select(IngestionJob, Document)
        .join(DocumentVersion, IngestionJob.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(IngestionJob.id == job_id, IngestionJob.tenant_id == principal.tenant_id,
               Document.tenant_id == principal.tenant_id)
    ).first()
    if not row:
        raise AppError("NOT_FOUND", "任务不存在或不可访问", 404)
    job, document = row
    require_kb(session, principal, document.knowledge_base_id)
    return job

