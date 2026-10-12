import os

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import KnowledgeBase, KnowledgeBaseMember, Tenant, User
from app.db.session import create_session_factory
from app.security.authentication import hash_password


def seed(factory, password):
    if len(password) < 12 or password.startswith("CHANGE_ME"):
        raise ValueError("DEMO_PASSWORD must contain at least 12 characters; change the placeholder")
    created = []
    with factory() as session:
        for name in ("customer-a", "customer-b"):
            tenant = session.scalar(select(Tenant).where(Tenant.name == name))
            if tenant:
                continue
            tenant = Tenant(name=name)
            session.add(tenant)
            session.flush()
            kb = KnowledgeBase(tenant_id=tenant.id, name="技术支持知识库")
            session.add(kb)
            session.flush()
            for username, role in (("admin", "admin"), ("reader", "member")):
                user = User(tenant_id=tenant.id, username=username, role=role,
                            password_hash=hash_password(password))
                session.add(user)
                session.flush()
                session.add(KnowledgeBaseMember(
                    tenant_id=tenant.id, knowledge_base_id=kb.id, user_id=user.id,
                ))
            created.append({"tenant": name, "knowledge_base_id": kb.id})
        session.commit()
    return created


def main():
    settings = get_settings()
    engine, factory = create_session_factory(settings.database_url)
    try:
        print(seed(factory, os.environ.get("DEMO_PASSWORD", "")))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

