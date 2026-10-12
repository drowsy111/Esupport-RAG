from sqlalchemy import delete

from app.db.models import KnowledgeBaseMember
from tests.conftest import authenticate, upload


def test_unauthenticated_request_is_denied(environment):
    response = environment.client.post("/api/v1/search", json={"query": "anything"})
    assert response.status_code == 401


def test_cross_tenant_document_job_and_kb_are_denied(environment):
    env = environment
    a, b = authenticate(env), authenticate(env, "b")
    ids = upload(env, a).json()
    assert env.client.get(f"/api/v1/documents/{ids['document_id']}", headers=b).status_code == 404
    assert env.client.get(f"/api/v1/jobs/{ids['job_id']}", headers=b).status_code == 404
    response = env.client.post("/api/v1/search", headers=b, json={
        "query": "anything", "knowledge_base_id": env.ids["a_kb"],
    })
    assert response.status_code == 404


def test_untrusted_vector_hits_never_reach_reranker_or_llm(environment):
    env = environment
    upload(env, authenticate(env), text="# SECRET-CUSTOMER-A\nPRIVATE-DEPLOYMENT")
    env.resources.vectors.include_foreign = True
    response = env.client.post("/api/v1/chat/completions", headers=authenticate(env, "b"),
                               json={"query": "部署说明"})
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_evidence"
    assert env.resources.reranker.seen == []
    assert env.resources.llm.calls == []


def test_member_cannot_upload(environment):
    env = environment
    response = upload(env, authenticate(env, username="member"))
    assert response.status_code == 403


def test_client_cannot_override_tenant(environment):
    env = environment
    response = env.client.post("/api/v1/search", headers=authenticate(env), json={
        "query": "anything", "tenant_id": env.ids["b_tenant"],
    })
    assert response.status_code == 422


def test_permission_revoked_during_generation_prevents_answer_return(environment):
    env = environment
    upload(env, authenticate(env))
    member = authenticate(env, username="member")

    def revoke():
        with env.factory() as session:
            session.execute(delete(KnowledgeBaseMember).where(
                KnowledgeBaseMember.user_id == env.ids["a_member"],
            ))
            session.commit()

    env.resources.llm.hook = revoke
    response = env.client.post("/api/v1/chat/completions", headers=member,
                               json={"query": "检查网络"})
    assert response.status_code == 409
    assert response.json()["code"] == "EVIDENCE_CHANGED"

