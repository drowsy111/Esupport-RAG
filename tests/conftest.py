from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.config import Settings
from app.db.base import Base
from app.db.models import KnowledgeBase, KnowledgeBaseMember, Tenant, User
from app.db.session import create_session_factory
from app.main import create_app
from app.security.authentication import hash_password
from app.services.ingestion_service import run_ingestion
from app.services.resources import Resources
from tests.fakes import (
    CharacterTokenizer, EvidenceLLM, FixedEmbedding, MemoryStorage, MemoryVectors, RecordingReranker,
)


@pytest.fixture(scope="session")
def password_hash():
    return hash_password("test-password-123")


@pytest.fixture
def environment(tmp_path, password_hash):
    settings = Settings(
        _env_file=None, database_url=f"sqlite:///{tmp_path / 'test.db'}",
        jwt_secret="test-only-random-secret-with-at-least-32-characters",
    )
    engine, factory = create_session_factory(settings.database_url)

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    ids = {}
    with factory() as session:
        for suffix in ("a", "b"):
            tenant = Tenant(name=f"customer-{suffix}")
            session.add(tenant)
            session.flush()
            kb = KnowledgeBase(tenant_id=tenant.id, name=f"KB {suffix}")
            session.add(kb)
            session.flush()
            for role in ("admin", "member"):
                user = User(
                    tenant_id=tenant.id, username=role, password_hash=password_hash, role=role,
                )
                session.add(user)
                session.flush()
                session.add(KnowledgeBaseMember(
                    tenant_id=tenant.id, knowledge_base_id=kb.id, user_id=user.id,
                ))
                ids[f"{suffix}_{role}"] = user.id
            ids[f"{suffix}_tenant"], ids[f"{suffix}_kb"] = tenant.id, kb.id
        session.commit()
    resources = Resources(
        MemoryStorage(), FixedEmbedding(), RecordingReranker(), MemoryVectors(),
        EvidenceLLM(), None,
    )
    resources.dispatch = lambda job_id: run_ingestion(
        job_id, factory, resources, settings, CharacterTokenizer(),
    )

    @asynccontextmanager
    async def lifespan(app):
        app.state.settings = settings
        app.state.session_factory = factory
        app.state.resources = resources
        yield

    app = create_app(settings, lifespan_override=lifespan)
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client, settings=settings, resources=resources, factory=factory, ids=ids,
        )
    engine.dispose()


def authenticate(env, suffix="a", username="admin"):
    result = env.client.post("/api/v1/auth/login", json={
        "tenant_name": f"customer-{suffix}", "username": username, "password": "test-password-123",
    })
    assert result.status_code == 200, result.text
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def upload(env, headers, suffix="a", text="# Support\n\nCheck network DEMO-001.", **metadata):
    return env.client.post(
        "/api/v1/documents/upload", headers=headers,
        data={"knowledge_base_id": env.ids[f"{suffix}_kb"], **metadata},
        files={"file": ("guide.md", text.encode(), "text/markdown")},
    )

