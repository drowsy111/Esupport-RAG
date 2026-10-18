
from app.core.exceptions import AppError
from app.schemas.query_plan import QueryPlan
from tests.conftest import authenticate, upload


def test_direct_plan_retrieves_original_query_unchanged(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers)
    env.resources.embedding.encoded.clear()
    env.resources.vectors.search_calls.clear()

    response = env.client.post(
        "/api/v1/chat/completions", headers=headers, json={"query": "检查网络"},
    )

    assert response.status_code == 200, response.text
    assert env.resources.embedding.encoded[-1] == (["检查网络"], "queries")
    assert len(env.resources.vectors.search_calls) == 1
    assert env.resources.reranker.queries == ["检查网络"]
    assert response.json()["trace"]["query_plan_route"] == "direct"


def test_decompose_retrieves_original_and_subqueries_then_reranks_original(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers)
    env.resources.llm.query_plan = QueryPlan(
        route="decompose",
        sub_queries=["如何备份配置？", "如何确认服务状态？"],
    )
    env.resources.embedding.encoded.clear()
    env.resources.vectors.search_calls.clear()

    response = env.client.post(
        "/api/v1/chat/completions",
        headers=headers,
        json={"query": "如何备份配置并确认服务状态？"},
    )

    assert response.status_code == 200, response.text
    assert env.resources.embedding.encoded[-1] == (
        ["如何备份配置并确认服务状态？", "如何备份配置？", "如何确认服务状态？"],
        "queries",
    )
    assert len(env.resources.vectors.search_calls) == 3
    assert env.resources.reranker.queries == ["如何备份配置并确认服务状态？"]
    assert response.json()["trace"]["query_plan_route"] == "decompose"
    assert response.json()["trace"]["query_plan_subqueries"] == 2


def test_clarify_plan_skips_retrieval_and_answer_generation(environment):
    env = environment
    headers = authenticate(env)
    env.resources.llm.query_plan = QueryPlan(
        route="clarify", clarification_message="你希望总结、解释还是排查这个标题？",
    )
    env.resources.embedding.encoded.clear()
    env.resources.vectors.search_calls.clear()

    response = env.client.post(
        "/api/v1/chat/completions", headers=headers, json={"query": "部署指南"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "needs_clarification"
    assert response.json()["answer"] == "你希望总结、解释还是排查这个标题？"
    assert env.resources.embedding.encoded == []
    assert env.resources.vectors.search_calls == []
    assert env.resources.llm.calls == []


def test_planner_error_falls_back_to_direct_retrieval(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers)
    env.resources.llm.plan_error = AppError("LLM_TIMEOUT", "planner timeout", 504)
    env.resources.embedding.encoded.clear()
    env.resources.vectors.search_calls.clear()

    response = env.client.post(
        "/api/v1/chat/completions", headers=headers, json={"query": "检查网络"},
    )

    assert response.status_code == 200, response.text
    assert env.resources.embedding.encoded[-1] == (["检查网络"], "queries")
    assert len(env.resources.vectors.search_calls) == 1
    assert response.json()["trace"]["query_plan_route"] == "direct"
    assert response.json()["trace"]["query_plan_fallback"] is True
    assert response.json()["trace"]["query_plan_error"] == "LLM_TIMEOUT"


def test_planner_receives_only_recent_messages_from_authorized_conversation(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers)
    first = env.client.post(
        "/api/v1/chat/completions", headers=headers, json={"query": "检查网络"},
    )
    conversation_id = first.json()["conversation_id"]

    second = env.client.post(
        "/api/v1/chat/completions", headers=headers,
        json={"query": "怎么确认它恢复了？", "conversation_id": conversation_id},
    )

    assert second.status_code == 200, second.text
    assert env.resources.llm.plan_calls[-1]["history"] == [
        {"role": "user", "content": "检查网络"},
        {"role": "assistant", "content": first.json()["answer"]},
    ]


def test_planner_can_be_disabled_and_uses_direct_retrieval(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers)
    env.settings.query_planner_enabled = False

    response = env.client.post(
        "/api/v1/chat/completions", headers=headers, json={"query": "检查网络"},
    )

    assert response.status_code == 200, response.text
    assert env.resources.llm.plan_calls == []
    assert response.json()["trace"]["query_plan_route"] == "direct"
    assert response.json()["trace"]["query_plan_source"] == "disabled"
