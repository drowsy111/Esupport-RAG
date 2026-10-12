from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import Settings


def test_upgrade_retains_legacy_chunk_and_downgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setattr("app.core.config.get_settings", lambda: Settings(
        _env_file=None, database_url=url,
    ))
    config = Config("alembic.ini")
    command.upgrade(config, "0002")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO chunks
                    (id, tenant_id, knowledge_base_id, document_id, version_id,
                     chunk_index, text, title_path, page, anchor, content_hash, token_count)
                VALUES ('legacy', 'tenant', 'kb', 'doc', 'version',
                        0, 'original text', '', 3, 'page-3', 'hash', 2)
            """))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            row = connection.execute(text(
                "SELECT text, page, structure FROM chunks WHERE id='legacy'",
            )).one()
            assert tuple(row) == ("original text", 3, None)
        command.downgrade(config, "0002")
        assert "structure" not in {c["name"] for c in inspect(engine).get_columns("chunks")}
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT text FROM chunks")) == "original text"
    finally:
        engine.dispose()
