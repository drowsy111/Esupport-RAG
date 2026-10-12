from sqlalchemy import select

from app.db.models import Chunk, DocumentVersion
from tests.conftest import authenticate, upload

BODY = "# 操作\n\n备份配置。\n\n执行迁移。\n\n检查状态。\n\n# 其他章节\n\n无关内容。"


def select_only_migration_hit(env):
    with env.factory() as session:
        core = session.scalar(select(Chunk).where(Chunk.text == "执行迁移。"))
        hit = {"id": core.id, "content_hash": core.content_hash, "score": 0.9}
    env.resources.vectors.search = lambda *args, **kwargs: [hit]
    return hit


def test_window_reaches_reranker_llm_and_citations(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers, text=BODY)
    hit = select_only_migration_hit(env)
    response = env.client.post("/api/v1/chat/completions", headers=headers,
                               json={"query": "迁移操作"})
    assert response.status_code == 200, response.text
    citation = response.json()["citations"][0]
    assert citation["matched_text"] == "执行迁移。"
    assert citation["chunk_id"] == hit["id"]
    assert "备份配置。" in citation["quote"] and "检查状态。" in citation["quote"]
    assert "无关内容" not in citation["quote"]
    assert len(citation["sources"]) >= 3
    assert env.resources.llm.calls[0][0]["text"] == citation["quote"]
    assert env.resources.reranker.seen[0] == "操作\n" + citation["quote"]


def test_neighbor_text_change_during_generation_invalidates_whole_window(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers, text=BODY)
    select_only_migration_hit(env)

    def mutate():
        with env.factory() as session:
            neighbor = session.scalar(select(Chunk).where(Chunk.text == "备份配置。"))
            # Even an out-of-band update that neglects content_hash is detected.
            neighbor.text = "已修改的内容"
            session.commit()

    env.resources.llm.hook = mutate
    response = env.client.post("/api/v1/chat/completions", headers=headers,
                               json={"query": "迁移操作"})
    assert response.status_code == 409
    assert response.json()["code"] == "EVIDENCE_CHANGED"


def test_new_version_publication_during_generation_invalidates_window(environment):
    env = environment
    headers = authenticate(env)
    ids = upload(env, headers, text=BODY).json()
    select_only_migration_hit(env)

    def supersede():
        with env.factory() as session:
            session.get(DocumentVersion, ids["version_id"]).publication_status = "SUPERSEDED"
            session.commit()

    env.resources.llm.hook = supersede
    response = env.client.post("/api/v1/chat/completions", headers=headers,
                               json={"query": "迁移操作"})
    assert response.status_code == 409


def test_unauthorized_neighbor_is_not_sent_to_models(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers, text=BODY)
    select_only_migration_hit(env)
    with env.factory() as session:
        neighbor = session.scalar(select(Chunk).where(Chunk.text == "备份配置。"))
        neighbor.knowledge_base_id = env.ids["b_kb"]
        session.commit()
    response = env.client.post("/api/v1/chat/completions", headers=headers,
                               json={"query": "迁移操作"})
    assert response.status_code == 200, response.text
    assert "备份配置。" not in env.resources.reranker.seen[0]
    assert "备份配置。" not in env.resources.llm.calls[0][0]["text"]


def test_search_returns_reranked_window_and_legacy_still_works(environment):
    env = environment
    headers = authenticate(env)
    upload(env, headers, text=BODY)
    hit = select_only_migration_hit(env)
    response = env.client.post("/api/v1/search", headers=headers, json={"query": "迁移"})
    window = response.json()["candidates"][0]
    assert "备份配置。" in window["text"]
    assert window["rerank_score"] is not None
    with env.factory() as session:
        session.get(Chunk, hit["id"]).structure = None
        session.commit()
    response = env.client.post("/api/v1/search", headers=headers, json={"query": "迁移"})
    assert response.json()["candidates"][0]["text"] == "执行迁移。"
