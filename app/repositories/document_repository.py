from sqlalchemy import select

from app.core.exceptions import AppError
from app.db.models import Document, DocumentVersion
from app.security.permissions import require_kb


def get_document(session, principal, document_id):
    document = session.scalar(select(Document).where(
        Document.id == document_id, Document.tenant_id == principal.tenant_id,
        Document.deleted.is_(False),
    ))
    if not document:
        raise AppError("NOT_FOUND", "文档不存在或不可访问", 404)
    require_kb(session, principal, document.knowledge_base_id)
    version = session.scalar(select(DocumentVersion).where(
        DocumentVersion.document_id == document.id,
        DocumentVersion.tenant_id == principal.tenant_id,
    ).order_by(DocumentVersion.revision.desc()))
    return document, version

