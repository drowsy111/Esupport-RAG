import logging
from time import perf_counter

from sqlalchemy import case, select

from app.core.exceptions import AppError
from app.db.base import new_id, utcnow
from app.db.models import Conversation, Message
from app.generation.answer_policy import clarification_needed, smalltalk_response
from app.generation.citations import validate_and_render
from app.retrieval.context_builder import build_context
from app.schemas.chat import ChatResponse, GeneratedAnswer
from app.schemas.query_plan import QueryPlan
from app.services.retrieval_service import retrieve, revalidate

logger = logging.getLogger(__name__)


def chat(session, principal, resources, settings, request, request_id):
    """
    聊天服务函数，用于处理聊天请求并生成响应。

    参数:
    - session: 数据库会话
    - principal: 当前用户主体
    - resources: 资源依赖
    - settings: 应用设置
    - request: ChatRequest, 聊天请求体
    - request_id: 请求ID

    返回:
    - ChatResponse, 聊天响应
    """
    started = perf_counter()
    message_received_at = utcnow()
    is_new_conversation = not request.conversation_id
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
            created_at=message_received_at,
        )

    smalltalk = smalltalk_response(request.query)
    clarification = None if smalltalk else clarification_needed(request)
    mapping, trace = {}, {}
    planner_started = perf_counter()
    planner_fallback = False
    planner_error = None
    if smalltalk:
        plan = QueryPlan(route="direct")
        planner_source = "rule"
    elif clarification:
        plan = QueryPlan(route="clarify", clarification_message=clarification)
        planner_source = "policy"
    elif not settings.query_planner_enabled:
        plan = QueryPlan(route="direct")
        planner_source = "disabled"
    else:
        history = []
        if request.conversation_id:
            rows = session.execute(
                select(Message.role, Message.content)
                .where(
                    Message.tenant_id == principal.tenant_id,
                    Message.conversation_id == conversation.id,
                )
                .order_by(
                    Message.created_at.desc(),
                    case((Message.role == "assistant", 1), else_=0).desc(),
                    Message.id.desc(),
                )
                .limit(6)
            ).all()
            history = [
                {"role": row.role, "content": row.content[:1500]}
                for row in reversed(rows)
                if row.role in {"user", "assistant"}
            ]
        try:
            plan = resources.llm.plan_query(
                request.query, history=history,
                context=request.context.model_dump(exclude_none=True),
                request_id=request_id,
            )
            planner_source = "model"
        except AppError as exc:
            plan = QueryPlan(route="direct")
            planner_source = "fallback"
            planner_fallback = True
            planner_error = exc.code
            logger.warning(
                "query_plan_fallback request_id=%s error_code=%s",
                request_id, exc.code,
            )
    planner_ms = 0 if smalltalk else round((perf_counter() - planner_started) * 1000, 2)

    trace.update({
        "query_plan_route": "smalltalk" if smalltalk else plan.route,
        "query_plan_source": planner_source,
        "query_plan_fallback": planner_fallback,
        "query_plan_subqueries": len(plan.sub_queries),
        "query_plan_ms": planner_ms,
    })
    if smalltalk:
        trace["retrieval_skipped"] = True
        trace["answer_generation_skipped"] = True
    if planner_error:
        trace["query_plan_error"] = planner_error

    if smalltalk:
        result = GeneratedAnswer(status="smalltalk", message=smalltalk)
    elif plan.route == "clarify":
        result = GeneratedAnswer(
            status="needs_clarification", message=plan.clarification_message,
        )
    else:
        candidates, retrieval_trace = retrieve(
            session, principal, resources, settings, request,
            retrieval_queries=plan.sub_queries,
        )
        trace.update(retrieval_trace)
        candidates = revalidate(session, principal, candidates, request.context)
        session.commit()
        evidence, mapping = build_context(candidates, settings.context_char_budget)
        if not evidence:
            result = GeneratedAnswer(
                status="insufficient_evidence", message="在授权且适用的资料中未找到足够证据。",
            )
        else:
            result = resources.llm.generate(request.query, evidence, request_id=request_id)

    answer, citations = validate_and_render(result, mapping)
    if mapping:
        current = revalidate(session, principal, list(mapping.values()), request.context)
        if {c.chunk_id for c in current} != {c.chunk_id for c in mapping.values()}:
            raise AppError("EVIDENCE_CHANGED", "权限或资料已变化，请重新提问", 409)
    trace["total_ms"] = round((perf_counter() - started) * 1000, 2)
    trace["request_id"] = request_id
    if is_new_conversation:
        session.add(conversation)
    session.add_all([
        Message(tenant_id=principal.tenant_id, conversation_id=conversation.id,
                turn_id=request_id, role="user", content=request.query,
                created_at=message_received_at),
        Message(tenant_id=principal.tenant_id, conversation_id=conversation.id,
                turn_id=request_id, role="assistant", content=answer, created_at=utcnow(),
                details={
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
