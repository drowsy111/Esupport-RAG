import json

from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppError
from app.db.base import new_id
from app.db.models import (
    Document, DocumentVersion, IngestionJob, KnowledgeBase, UploadClaim, UploadReceipt,
)
from app.ingestion.identifiers import content_hash
from app.security.permissions import require_kb
from app.security.upload_validation import validate_upload


def dispatch_job(session, resources, job):
    try:
        resources.dispatch(job.id)
    except Exception:
        # Conditional update: broker may accept then timeout while worker already claimed the job.
        session.execute(update(IngestionJob).where(
            IngestionJob.id == job.id, IngestionJob.status == "QUEUED",
        ).values(status="FAILED", error_code="DISPATCH_FAILED"))
        session.commit()


def _digest(value):
    return content_hash(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _result(session, version_id, reused=False, replayed=False):
    version = session.get(DocumentVersion, version_id)
    job = session.scalar(select(IngestionJob).where(IngestionJob.version_id == version_id))
    return {"document_id": version.document_id, "version_id": version.id,
            "revision": version.revision, "job_id": job.id, "status": job.status,
            "error_code": job.error_code, "reused": reused, "replayed": replayed}


def upload_document(session, resources, settings, principal, kb_id, filename, data, metadata,
                    idempotency_key=None, document_id=None, allow_same_name=False):
    require_kb(session, principal, kb_id, write=True)
    name, file_type = validate_upload(filename, data, settings.upload_max_bytes)
    session.commit()  # End permission-read snapshot before waiting for a MySQL lock.
    # Serialize decisions within a KB in MySQL. Unique claim/receipt PKs also guard races.
    session.scalar(select(KnowledgeBase).where(
        KnowledgeBase.id == kb_id, KnowledgeBase.tenant_id == principal.tenant_id,
    ).with_for_update())
    require_kb(session, principal, kb_id, write=True)
    file_hash = content_hash(data)
    identity = [principal.tenant_id, kb_id, file_type, file_hash, metadata]
    claim_key = _digest(identity)
    fingerprint = _digest([identity, name, document_id, allow_same_name])
    receipt_key = _digest([principal.tenant_id, principal.user_id, kb_id, idempotency_key]) if idempotency_key else None
    if receipt_key:
        receipt = session.get(UploadReceipt, receipt_key)
        if receipt:
            if receipt.fingerprint != fingerprint:
                raise AppError("IDEMPOTENCY_CONFLICT", "同一幂等键不能用于不同上传请求", 409)
            version = session.get(DocumentVersion, receipt.version_id)
            if session.get(Document, version.document_id).deleted:
                raise AppError("DOCUMENT_DELETED", "原请求的文档已删除，请使用新的幂等键", 409)
            result = _result(session, receipt.version_id, True, True)
            session.commit()
            return result

    document = None
    if document_id:
        document = session.scalar(select(Document).where(
            Document.id == document_id, Document.tenant_id == principal.tenant_id,
            Document.knowledge_base_id == kb_id, Document.deleted.is_(False),
        ))
        if not document:
            raise AppError("NOT_FOUND", "待更新文档不存在或不可访问", 404)

    # Also find legacy uploads: migration intentionally does not delete or rewrite them.
    duplicate_query = select(DocumentVersion).join(Document).where(
        Document.tenant_id == principal.tenant_id, Document.knowledge_base_id == kb_id,
        Document.deleted.is_(False), DocumentVersion.file_hash == file_hash,
        DocumentVersion.file_type == file_type,
        DocumentVersion.publication_status != "SUPERSEDED",
    )
    for field, value in metadata.items():
        duplicate_query = duplicate_query.where(getattr(DocumentVersion, field) == value)
    if document_id:
        duplicate_query = duplicate_query.where(Document.id == document_id)
    duplicate = session.scalar(duplicate_query.order_by(
        (DocumentVersion.publication_status == "PUBLISHED").desc(),
        DocumentVersion.created_at, DocumentVersion.id,
    ).limit(1))
    if duplicate:
        if receipt_key:
            session.add(UploadReceipt(key=receipt_key, fingerprint=fingerprint, version_id=duplicate.id))
        result = _result(session, duplicate.id, True)
        session.commit()
        return result

    if document:
        pending = session.scalar(select(IngestionJob.id).join(DocumentVersion).where(
            DocumentVersion.document_id == document.id,
            IngestionJob.status.in_(["QUEUED", "RUNNING", "FAILED"]),
        ).limit(1))
        if pending:
            raise AppError("VERSION_PENDING", "已有未完成版本，请等待或重试原任务", 409)
        revision = session.scalar(select(func.max(DocumentVersion.revision)).where(
            DocumentVersion.document_id == document.id,
        )) + 1
        # Updating a particular document is distinct from deduplicating new documents.
        claim_key = _digest([claim_key, document.id])
    else:
        same_name = session.scalar(select(Document.id).where(
            Document.tenant_id == principal.tenant_id, Document.knowledge_base_id == kb_id,
            Document.name == name, Document.deleted.is_(False),
        ).limit(1))
        if same_name and not allow_same_name:
            raise AppError("DOCUMENT_NAME_CONFLICT", "同名文档已存在：指定 document_id 更新，或 allow_same_name=true 另存", 409)
        document = Document(id=new_id(), tenant_id=principal.tenant_id,
                            knowledge_base_id=kb_id, name=name)
        revision = 1
    document_id, version_id, job_id = document.id, new_id(), new_id()
    object_key = f"{principal.tenant_id}/{document_id}/{version_id}/source.{file_type}"
    version = DocumentVersion(
        id=version_id, tenant_id=principal.tenant_id, document_id=document_id,
        revision=revision, object_key=object_key, file_hash=file_hash, file_type=file_type, **metadata,
    )
    job = IngestionJob(id=job_id, tenant_id=principal.tenant_id, version_id=version_id)
    try:
        session.add(document)
        session.flush()
        session.add(version)
        session.flush()
        session.add(job)
        claim = session.get(UploadClaim, claim_key)
        if claim:
            claim.version_id = version_id
        else:
            session.add(UploadClaim(key=claim_key, version_id=version_id))
        if receipt_key:
            session.add(UploadReceipt(key=receipt_key, fingerprint=fingerprint, version_id=version_id))
        session.flush()
        resources.storage.put(object_key, data)
        session.commit()
    except Exception as exc:
        session.rollback()
        try:
            resources.storage.remove(object_key)
        except Exception:
            pass  # Lifecycle cleanup handles an orphan if compensation also fails.
        if isinstance(exc, IntegrityError):
            raise AppError("UPLOAD_CONFLICT", "并发上传冲突，请使用相同幂等键重试", 409) from exc
        raise
    dispatch_job(session, resources, job)
    session.refresh(job)
    return _result(session, version_id)


def retry_job(session, resources, principal, job):
    if principal.role != "admin":
        raise AppError("FORBIDDEN", "仅管理员可以重试任务", 403)
    result = session.execute(update(IngestionJob).where(
        IngestionJob.id == job.id, IngestionJob.tenant_id == principal.tenant_id,
        IngestionJob.status == "FAILED",
    ).values(status="QUEUED", error_code=None))
    if not result.rowcount:
        session.rollback()
        raise AppError("JOB_NOT_RETRYABLE", "仅 FAILED 任务可重试", 409)
    session.commit()
    dispatch_job(session, resources, job)
    session.refresh(job)
    return {"job_id": job.id, "status": job.status}
