from sqlalchemy import select

from app.core.exceptions import AppError
from app.db.models import KnowledgeBase, KnowledgeBaseMember


def allowed_knowledge_bases(session, principal) -> list[str]:
    stmt = select(KnowledgeBase.id).where(KnowledgeBase.tenant_id == principal.tenant_id)
    if principal.role != "admin":
        stmt = stmt.join(
            KnowledgeBaseMember,
            KnowledgeBaseMember.knowledge_base_id == KnowledgeBase.id,
        ).where(
            KnowledgeBaseMember.tenant_id == principal.tenant_id,
            KnowledgeBaseMember.user_id == principal.user_id,
        )
    return list(session.scalars(stmt))


def require_kb(session, principal, knowledge_base_id: str, write=False):
    if write and principal.role != "admin":
        raise AppError("FORBIDDEN", "仅管理员可上传或发布文档", 403)
    if knowledge_base_id not in allowed_knowledge_bases(session, principal):
        raise AppError("NOT_FOUND", "知识库不存在或不可访问", 404)

