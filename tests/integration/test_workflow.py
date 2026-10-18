from datetime import datetime

from sqlalchemy import func, select

from app.db.models import Chunk, Conversation, IngestionJob, Message, User
from app.services.ingestion_service import run_ingestion
from tests.conftest import authenticate, upload
from tests.fakes import CharacterTokenizer


def test_upload_search_answer_and_server_owned_citation(environment):
    env = environment
    headers = authenticate(env)
    response = upload(env, headers)
    assert response.status_code == 202, response.text
    ids = response.json()
    status = env.client.get(f"/api/v1/jobs/{ids['job_id']}", headers=headers)
    assert status.json()["status"] == "READY"
    search = env.client.post("/api/v1/search", headers=headers, json={"query": "DEMO-001"})
    assert search.status_code == 200, search.text
    assert search.json()["candidates"]
    answer = env.client.post("/api/v1/chat/completions", headers=headers, json={"query": "怎么检查网络"})
    assert answer.status_code == 200, answer.text
    data = answer.json()
    assert data["status"] == "answered"
    assert data["citations"][0]["document_id"] == ids["document_id"]
    assert data["citations"][0]["anchor"].startswith("L")
    assert data["citations"][0]["page"] is None
    assert data["citations"][0]["quote"] in "# Support\n\nCheck network DEMO-001."
    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(Message)) == 2
        messages = list(session.scalars(select(Message).where(
            Message.conversation_id == data["conversation_id"],
        )))
        by_role = {message.role: message for message in messages}
        assert by_role["user"].content == "怎么检查网络"
        assert by_role["assistant"].content == data["answer"]
        assert by_role["user"].turn_id == by_role["assistant"].turn_id == data["request_id"]
        assert by_role["user"].created_at <= by_role["assistant"].created_at
        conversation = session.get(Conversation, data["conversation_id"])
        assert conversation.created_at == by_role["user"].created_at


def test_failed_chat_does_not_leave_an_empty_conversation(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers)
    env.resources.llm.invalid = True

    response = env.client.post(
        "/api/v1/chat/completions", headers=headers, json={"query": "检查网络"},
    )

    assert response.status_code == 502
    with env.factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 0
        assert session.scalar(select(func.count()).select_from(Message)) == 0


def test_history_keeps_question_before_answer_when_timestamps_match(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers)
    with env.factory() as session:
        user = session.scalar(select(User).where(
            User.tenant_id == env.ids["a_tenant"], User.username == "admin",
        ))
        conversation = Conversation(tenant_id=user.tenant_id, user_id=user.id)
        session.add(conversation)
        session.flush()
        timestamp = datetime(2025, 1, 1)
        session.add_all([
            Message(
                tenant_id=user.tenant_id, conversation_id=conversation.id, turn_id="turn-1",
                role="user", content="先前的问题", created_at=timestamp,
            ),
            Message(
                tenant_id=user.tenant_id, conversation_id=conversation.id, turn_id="turn-1",
                role="assistant", content="先前的回答", created_at=timestamp,
            ),
        ])
        session.commit()

    response = env.client.post(
        "/api/v1/chat/completions", headers=headers,
        json={"query": "继续查询", "conversation_id": conversation.id},
    )

    assert response.status_code == 200, response.text
    assert env.resources.llm.plan_calls[-1]["history"] == [
        {"role": "user", "content": "先前的问题"},
        {"role": "assistant", "content": "先前的回答"},
    ]


def test_duplicate_job_delivery_does_not_duplicate_chunks(environment):
    env = environment
    ids = upload(env, authenticate(env)).json()
    before = len(env.resources.vectors.rows)
    run_ingestion(ids["job_id"], env.factory, env.resources, env.settings, CharacterTokenizer())
    assert len(env.resources.vectors.rows) == before
    with env.factory() as session:
        assert session.get(IngestionJob, ids["job_id"]).attempts == 1
        assert session.scalar(select(func.count()).select_from(Chunk)) == before


def test_vector_failure_can_be_retried(environment):
    env = environment
    headers = authenticate(env)
    env.resources.vectors.fail_next = True
    ids = upload(env, headers).json()
    assert env.client.get(f"/api/v1/jobs/{ids['job_id']}", headers=headers).json()["status"] == "FAILED"
    response = env.client.post(f"/api/v1/jobs/{ids['job_id']}/retry", headers=headers)
    assert response.status_code == 202
    assert env.client.get(f"/api/v1/jobs/{ids['job_id']}", headers=headers).json()["status"] == "READY"
    with env.factory() as session:
        assert session.get(IngestionJob, ids["job_id"]).attempts == 2


def test_no_evidence_does_not_call_llm(environment):
    env = environment
    response = env.client.post("/api/v1/chat/completions", headers=authenticate(env),
                               json={"query": "未知故障"})
    assert response.json()["status"] == "insufficient_evidence"
    assert env.resources.llm.calls == []


def test_smalltalk_skips_planning_and_retrieval_but_saves_the_turn(environment):
    env = environment
    response = env.client.post(
        "/api/v1/chat/completions", headers=authenticate(env), json={"query": "你好！"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "smalltalk"
    assert data["trace"]["query_plan_route"] == "smalltalk"
    assert data["trace"]["query_plan_source"] == "rule"
    assert data["trace"]["query_plan_ms"] == 0
    assert data["trace"]["retrieval_skipped"] is True
    assert env.resources.llm.plan_calls == []
    assert env.resources.llm.calls == []
    assert env.resources.embedding.encoded == []
    assert env.resources.vectors.search_calls == []
    with env.factory() as session:
        messages = list(session.scalars(select(Message).where(
            Message.conversation_id == data["conversation_id"],
        )))
        assert {message.role: message.content for message in messages} == {
            "user": "你好！", "assistant": data["answer"],
        }
        assert {message.turn_id for message in messages} == {data["request_id"]}


def test_short_error_code_still_uses_query_planner_and_retrieval(environment):
    env = environment
    response = env.client.post(
        "/api/v1/chat/completions", headers=authenticate(env), json={"query": "401"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "insufficient_evidence"
    assert env.resources.llm.plan_calls
    assert env.resources.embedding.encoded


def test_upgrade_requires_version(environment):
    env = environment
    response = env.client.post("/api/v1/chat/completions", headers=authenticate(env),
                               json={"query": "如何升级？"})
    assert response.json()["status"] == "needs_clarification"
    assert env.resources.llm.calls == []


def test_invented_citation_is_rejected(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers)
    env.resources.llm.invalid = True
    response = env.client.post("/api/v1/chat/completions", headers=headers, json={"query": "检查网络"})
    assert response.status_code == 502
    assert response.json()["code"] == "INVALID_CITATION"


def test_version_filter_is_checked_against_mysql(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers, product_version="2.3.0")
    response = env.client.post("/api/v1/search", headers=headers, json={
        "query": "检查网络", "context": {"product_version": "2.4.1"},
    })
    assert response.json()["candidates"] == []


def test_openapi_contains_expected_routes(environment):
    paths = environment.client.get("/openapi.json").json()["paths"]
    assert {"/api/v1/documents/upload", "/api/v1/search", "/api/v1/chat/completions"} <= set(paths)
