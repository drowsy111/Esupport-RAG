import logging

from sqlalchemy import delete, update

from app.core.exceptions import AppError
from app.db.models import Chunk, Document, DocumentVersion, IngestionJob
from app.ingestion.chunking import load_tokenizer
from app.ingestion.identifiers import chunk_id, content_hash
from app.ingestion.pipeline import parse_and_chunk

logger = logging.getLogger(__name__)


def run_ingestion(job_id, factory, resources, settings, tokenizer=None):
    with factory() as session:
        claimed = session.execute(update(IngestionJob).where(
            IngestionJob.id == job_id, IngestionJob.status == "QUEUED",
        ).values(status="RUNNING", stage="PARSING",
                 attempts=IngestionJob.attempts + 1, error_code=None))
        session.commit()
        if not claimed.rowcount:
            return  # Redelivery cannot race a running or completed job.
        job = session.get(IngestionJob, job_id)
        version = session.get(DocumentVersion, job.version_id)
        document = session.get(Document, version.document_id)

        def stage(value):
            job.stage = value
            version.status = value
            session.commit()

        try:
            stage("PARSING")
            data = resources.storage.get(version.object_key)
            if content_hash(data) != version.file_hash:
                raise AppError("SOURCE_HASH_MISMATCH", "源文件完整性校验失败")
            if tokenizer is None:
                tokenizer = load_tokenizer(settings.embedding_model, settings.embedding_revision)
            stage("CHUNKING")
            parsed, drafts = parse_and_chunk(data, version.file_type, tokenizer, settings)
            # Deleting only this unready version is safe; subsequent retries regenerate stable IDs.
            session.execute(delete(Chunk).where(
                Chunk.version_id == version.id, Chunk.tenant_id == version.tenant_id,
            ))
            chunks = [
                Chunk(
                    id=chunk_id(version.tenant_id, version.id, i, draft.text),
                    tenant_id=version.tenant_id, knowledge_base_id=document.knowledge_base_id,
                    document_id=document.id, version_id=version.id, chunk_index=i,
                    text=draft.text, title_path=draft.title_path, page=draft.page,
                    anchor=draft.anchor, token_count=draft.token_count,
                    content_hash=content_hash(draft.text),
                    structure=draft.structure,
                ) for i, draft in enumerate(drafts)
            ]
            session.add_all(chunks)
            version.warnings = parsed.warnings
            stage("EMBEDDING")
            embeddings = resources.embedding.encode([
                (c.title_path[:60] + "\n" + c.text) if c.title_path else c.text for c in chunks
            ])
            stage("INDEXING")
            rows = []
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                rows.append({
                    "id": chunk.id, "tenant_id": chunk.tenant_id,
                    "knowledge_base_id": chunk.knowledge_base_id,
                    "document_id": chunk.document_id, "version_id": version.id,
                    "content_hash": chunk.content_hash, "is_active": True,
                    "publication_status": "PUBLISHED",
                    "embedding_version": settings.embedding_version,
                    "product_id": version.product_id, "product_version": version.product_version,
                    "deployment_mode": version.deployment_mode,
                    "dense_vector": embedding.dense, "sparse_vector": embedding.sparse,
                })
            resources.vectors.upsert(rows)
            # SQL is authoritative: switch versions only after successful indexing.
            session.execute(update(DocumentVersion).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.tenant_id == version.tenant_id,
                DocumentVersion.id != version.id,
                DocumentVersion.publication_status == "PUBLISHED",
            ).values(publication_status="SUPERSEDED"))
            job.status, job.stage = "READY", "READY"
            version.status, version.publication_status = "READY", "PUBLISHED"
            session.commit()
        except Exception as exc:
            session.rollback()
            code = exc.code if isinstance(exc, AppError) else "INGESTION_FAILED"
            session.execute(update(IngestionJob).where(
                IngestionJob.id == job_id,
            ).values(status="FAILED", error_code=code))
            session.execute(update(DocumentVersion).where(
                DocumentVersion.id == version.id,
            ).values(status="FAILED", publication_status="DRAFT"))
            session.commit()
            logger.warning("ingestion_failed job_id=%s code=%s type=%s",
                           job_id, code, type(exc).__name__)
