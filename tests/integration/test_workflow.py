from sqlalchemy import func, select

from app.db.models import Chunk, IngestionJob, Message
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

