from time import perf_counter

from sqlalchemy import select

from app.core.exceptions import AppError
from app.db.base import new_id
from app.db.models import Conversation, Message
from app.generation.answer_policy import clarification_needed
from app.generation.citations import validate_and_render
from app.retrieval.context_builder import build_context
from app.schemas.chat import ChatResponse, GeneratedAnswer
from app.services.retrieval_service import retrieve, revalidate


def chat(session, principal, resources, settings, request, request_id):
    started = perf_counter()
    if request.conversation_id:
        conversation = session.scalar(select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.tenant_id == principal.tenant_id,
            Conversation.user_id == principal.user_id,
        ))
        if not conversation:
            raise AppError("NOT_FOUND", "会话不存在或不可访问", 404)
    else:
        conversation = Conversation(
            id=new_id(), tenant_id=principal.tenant_id, user_id=principal.user_id,
        )
        session.add(conversation)
        session.commit()

    clarification = clarification_needed(request)
    mapping, trace = {}, {}
    if clarification:
        result = GeneratedAnswer(status="needs_clarification", message=clarification)
    else:
        candidates, trace = retrieve(session, principal, resources, settings, request)
        candidates = revalidate(session, principal, candidates, request.context)
        session.commit()
        evidence, mapping = build_context(candidates, settings.context_char_budget)
        if not evidence:
            result = GeneratedAnswer(
                status="insufficient_evidence", message="在授权且适用的资料中未找到足够证据。",
            )
        else:
            result = resources.llm.generate(request.query, evidence)

    answer, citations = validate_and_render(result, mapping)
    if mapping:
        current = revalidate(session, principal, list(mapping.values()), request.context)
        if {c.chunk_id for c in current} != {c.chunk_id for c in mapping.values()}:
            raise AppError("EVIDENCE_CHANGED", "权限或资料已变化，请重新提问", 409)
    trace["total_ms"] = round((perf_counter() - started) * 1000, 2)
    trace["request_id"] = request_id
    session.add_all([
        Message(tenant_id=principal.tenant_id, conversation_id=conversation.id,
                role="user", content=request.query),
        Message(tenant_id=principal.tenant_id, conversation_id=conversation.id,
                role="assistant", content=answer, details={
                    "status": result.status, "trace": trace,
                    "citations": [c.model_dump() for c in citations],
                    "claims": [claim.model_dump() for claim in result.claims],
                }),
    ])
    session.commit()
    return ChatResponse(
        request_id=request_id, conversation_id=conversation.id,
        status=result.status, answer=answer, citations=citations, trace=trace,
    )

