from sqlalchemy import and_, or_, select

from app.db.models import Chunk, Document, DocumentVersion
from app.schemas.retrieval import Candidate


def authorized_candidates(session, principal, kb_ids, hits, context):
    if not hits or not kb_ids:
        return []
    stmt = (
        select(Chunk, Document, DocumentVersion)
        .join(Document, Chunk.document_id == Document.id)
        .join(DocumentVersion, Chunk.version_id == DocumentVersion.id)
        .where(
            Chunk.id.in_([h["id"] for h in hits]), Chunk.tenant_id == principal.tenant_id,
            Chunk.knowledge_base_id.in_(kb_ids), Document.tenant_id == principal.tenant_id,
            DocumentVersion.tenant_id == principal.tenant_id, Document.deleted.is_(False),
            DocumentVersion.status == "READY", DocumentVersion.publication_status == "PUBLISHED",
        )
    )
    for field in ("product_id", "product_version", "deployment_mode"):
        value = getattr(context, field, None)
        if value:
            column = getattr(DocumentVersion, field)
            stmt = stmt.where(column.in_([value, ""]))
    records = {c.id: (c, d, v) for c, d, v in session.execute(stmt)}
    candidates = []
    for hit in hits:
        row = records.get(hit["id"])
        if not row:
            continue
        chunk, document, version = row
        if hit.get("content_hash") != chunk.content_hash:
            continue
        candidates.append(Candidate(
            chunk_id=chunk.id, document_id=document.id, version_id=version.id,
            document_name=document.name, revision=version.revision, text=chunk.text,
            content_hash=chunk.content_hash, page=chunk.page, anchor=chunk.anchor,
            title_path=chunk.title_path, source_kind=version.source_kind,
            product_version=version.product_version, fusion_score=hit.get("score", 0),
            chunk_index=chunk.chunk_index, token_count=chunk.token_count,
            structure=chunk.structure, matched_text=chunk.text,
            matched_chunk_ids=[chunk.id],
        ))
    return candidates


def authorized_neighbors(session, principal, kb_ids, candidates, context, radius):
    """Bounded SQL range lookup, followed by the same authorization as vector hits."""
    ranges = [and_(
        Chunk.version_id == c.version_id, Chunk.document_id == c.document_id,
        Chunk.chunk_index.between(c.chunk_index - radius, c.chunk_index + radius),
    ) for c in candidates if c.structure]
    if not ranges:
        return []
    rows = session.execute(select(Chunk.id, Chunk.content_hash).where(
        Chunk.tenant_id == principal.tenant_id,
        Chunk.knowledge_base_id.in_(kb_ids), or_(*ranges),
    ))
    hits = [{"id": row.id, "content_hash": row.content_hash} for row in rows]
    return authorized_candidates(session, principal, kb_ids, hits, context)

