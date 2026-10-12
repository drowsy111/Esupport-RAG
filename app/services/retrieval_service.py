from time import perf_counter

from sqlalchemy import select

from app.db.models import Document, DocumentVersion
from app.repositories.chunk_repository import authorized_candidates, authorized_neighbors
from app.retrieval.deduplication import deduplicate
from app.retrieval.reranking import rerank
from app.retrieval.sentence_window import make_windows
from app.security.permissions import allowed_knowledge_bases, require_kb


def retrieve(session, principal, resources, settings, request):
    """
    """
    started = perf_counter()
    if request.knowledge_base_id:
        require_kb(session, principal, request.knowledge_base_id)
        kb_ids = [request.knowledge_base_id]
    else:
        kb_ids = allowed_knowledge_bases(session, principal)
    if not kb_ids:
        return [], {"retrieved": 0, "selected": 0}
    published_versions = list(session.scalars(select(DocumentVersion.id).join(Document).where(
        Document.tenant_id == principal.tenant_id, Document.knowledge_base_id.in_(kb_ids),
        Document.deleted.is_(False), DocumentVersion.status == "READY",
        DocumentVersion.publication_status == "PUBLISHED",
    )))
    session.commit()  # Release DB transaction before remote calls.
    embedding = resources.embedding.encode([request.query], kind="queries")[0]
    encoded_at = perf_counter()
    hits = resources.vectors.search(
        embedding, principal.tenant_id, kb_ids, request.context,
        published_version_ids=published_versions,
    )
    recalled_at = perf_counter()
    # Fresh authorization and authoritative content before sending any text to model services.
    session.expire_all()
    permitted = set(allowed_knowledge_bases(session, principal)) & set(kb_ids)
    candidates = authorized_candidates(session, principal, permitted, hits, request.context)
    candidates = deduplicate(candidates)
    neighbors = authorized_neighbors(
        session, principal, permitted, candidates, request.context, settings.window_neighbors,
    )
    session.commit()
    windows = make_windows(
        candidates, neighbors, settings.window_neighbors, settings.window_max_tokens,
    )
    result = rerank(request.query, windows, resources.reranker, settings.context_top_k)
    return result, {
        "retrieved": len(candidates), "selected": len(result),
        "windows": len(windows),
        "embedding_ms": round((encoded_at - started) * 1000, 2),
        "retrieval_ms": round((recalled_at - encoded_at) * 1000, 2),
        "rerank_ms": round((perf_counter() - recalled_at) * 1000, 2),
        "collection": settings.milvus_collection, "embedding_version": settings.embedding_version,
    }


def revalidate(session, principal, candidates, context):
    session.commit()
    session.expire_all()
    kb_ids = allowed_knowledge_bases(session, principal)
    sources = {s.chunk_id: s for c in candidates for s in (c.sources or [c.as_source()])}
    hits = [{"id": s.chunk_id, "content_hash": s.content_hash} for s in sources.values()]
    current = {c.chunk_id: c for c in authorized_candidates(
        session, principal, kb_ids, hits, context,
    )}
    # Preserve expanded text and rerank order only if EVERY constituent is unchanged.
    return [c for c in candidates if all(
        s.chunk_id in current and current[s.chunk_id].as_source() == s
        and current[s.chunk_id].version_id == c.version_id
        and current[s.chunk_id].document_id == c.document_id
        and current[s.chunk_id].revision == c.revision
        and current[s.chunk_id].document_name == c.document_name
        and current[s.chunk_id].product_version == c.product_version
        and current[s.chunk_id].source_kind == c.source_kind
        for s in (c.sources or [c.as_source()])
    )]
