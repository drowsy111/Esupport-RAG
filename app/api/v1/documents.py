"""
文件说明: 该模块定义了FastAPI应用的文档相关路由，包括列出文档和上传文档的接口。
"""

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from sqlalchemy import func, select

from app.api.dependencies import (
    current_principal, get_resources, get_session, get_settings_dependency,
)
from app.db.models import Document, DocumentVersion, IngestionJob
from app.security.permissions import require_kb
from app.repositories.document_repository import get_document
from app.services.document_service import upload_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
def list_documents(
    knowledge_base_id: str, page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session=Depends(get_session), principal=Depends(current_principal),
):
    require_kb(session, principal, knowledge_base_id)
    scope = [Document.tenant_id == principal.tenant_id,
             Document.knowledge_base_id == knowledge_base_id, Document.deleted.is_(False)]
    total = session.scalar(select(func.count()).select_from(Document).where(*scope))
    documents = list(session.scalars(select(Document).where(*scope).order_by(
        Document.created_at.desc(), Document.id,
    ).offset((page - 1) * page_size).limit(page_size)))
    ids = [d.id for d in documents]
    versions = list(session.scalars(select(DocumentVersion).where(
        DocumentVersion.tenant_id == principal.tenant_id,
        DocumentVersion.document_id.in_(ids),
    ).order_by(DocumentVersion.revision.desc()))) if ids else []
    latest, published = {}, {}
    for version in versions:
        latest.setdefault(version.document_id, version)
        if version.status == "READY" and version.publication_status == "PUBLISHED":
            published.setdefault(version.document_id, version.id)
    jobs = {j.version_id: j for j in session.scalars(select(IngestionJob).where(
        IngestionJob.tenant_id == principal.tenant_id,
        IngestionJob.version_id.in_([v.id for v in latest.values()]),
    ))} if latest else {}
    items = []
    for document in documents:
        version = latest.get(document.id)
        job = jobs.get(version.id) if version else None
        items.append({
            "id": document.id, "name": document.name, "knowledge_base_id": knowledge_base_id,
            "revision": version.revision if version else None,
            "version_id": version.id if version else None,
            "published_version_id": published.get(document.id),
            "status": job.status if job else "UNKNOWN", "stage": job.stage if job else None,
            "job_id": job.id if job else None, "error_code": job.error_code if job else None,
            "product_id": version.product_id if version else "",
            "product_version": version.product_version if version else "",
            "deployment_mode": version.deployment_mode if version else "",
            "source_kind": version.source_kind if version else "uploaded",
            "source_url": version.source_url if version else "",
            "created_at": document.created_at,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/upload", status_code=202)
def upload(
    file: UploadFile = File(...), knowledge_base_id: str = Form(...),
    product_id: str = Form("", max_length=100),
    product_version: str = Form("", max_length=50),
    deployment_mode: str = Form("", max_length=50),
    source_kind: Literal["uploaded", "synthetic", "official"] = Form("uploaded"),
    source_url: str = Form("", max_length=1000),
    document_id: str | None = Form(None, max_length=36),
    allow_same_name: bool = Form(False),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key", min_length=1, max_length=128),
    session=Depends(get_session), principal=Depends(current_principal),
    resources=Depends(get_resources), settings=Depends(get_settings_dependency),
):
    try:
        data = file.file.read(settings.upload_max_bytes + 1)
    finally:
        file.file.close()
    return upload_document(
        session, resources, settings, principal, knowledge_base_id, file.filename or "", data,
        {"product_id": product_id, "product_version": product_version,
         "deployment_mode": deployment_mode, "source_kind": source_kind, "source_url": source_url},
        idempotency_key=idempotency_key, document_id=document_id, allow_same_name=allow_same_name,
    )


@router.get("/{document_id}")
def detail(document_id: str, session=Depends(get_session), principal=Depends(current_principal)):
    document, version = get_document(session, principal, document_id)
    return {
        "id": document.id, "name": document.name, "knowledge_base_id": document.knowledge_base_id,
        "revision": version.revision, "version_id": version.id, "status": version.status,
        "publication_status": version.publication_status,
        "product_id": version.product_id, "product_version": version.product_version,
        "deployment_mode": version.deployment_mode, "warnings": version.warnings,
        "published_version_id": session.scalar(select(DocumentVersion.id).where(
            DocumentVersion.document_id == document.id,
            DocumentVersion.publication_status == "PUBLISHED",
            DocumentVersion.status == "READY",
        ).order_by(DocumentVersion.revision.desc()).limit(1)),
    }


@router.get("/{document_id}/status")
def status(document_id: str, session=Depends(get_session), principal=Depends(current_principal)):
    _, version = get_document(session, principal, document_id)
    job = session.scalar(select(IngestionJob).where(
        IngestionJob.version_id == version.id, IngestionJob.tenant_id == principal.tenant_id,
    ))
    return {"job_id": job.id, "status": job.status, "stage": job.stage,
            "attempts": job.attempts, "error_code": job.error_code}
