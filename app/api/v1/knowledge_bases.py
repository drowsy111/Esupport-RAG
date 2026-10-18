"""
文件说明: 该模块定义了FastAPI应用的知识库相关路由，包括列出知识库的接口。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.dependencies import current_principal, get_session
from app.db.models import KnowledgeBase
from app.security.permissions import allowed_knowledge_bases

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.get("")
def list_knowledge_bases(session=Depends(get_session), principal=Depends(current_principal)):
    ids = allowed_knowledge_bases(session, principal)
    rows = session.scalars(select(KnowledgeBase).where(
        KnowledgeBase.id.in_(ids), KnowledgeBase.tenant_id == principal.tenant_id,
    ))
    return [{"id": row.id, "name": row.name} for row in rows]

