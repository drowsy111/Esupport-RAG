import importlib.util
import sys
import types
from pathlib import Path

from sqlalchemy import Column, Index, MetaData, Table, create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.db.base import Base


def test_frozen_migration_matches_orm_definition(monkeypatch):
    """Validate migration's table/index definitions; not an Alembic runner integration test."""
    metadata = MetaData()

    class Operations:
        @staticmethod
        def create_table(name, *columns):
            Table(name, metadata, *columns)

        @staticmethod
        def create_index(name, table, columns):
            Index(name, *[metadata.tables[table].c[c] for c in columns])

        @staticmethod
        def add_column(table, column):
            metadata.tables[table].append_column(column)

        @staticmethod
        def alter_column(table, column, type_, **kwargs):
            metadata.tables[table].c[column].type = type_

        @staticmethod
        def get_bind():
            return types.SimpleNamespace(dialect=types.SimpleNamespace(name="mysql"))

    module = types.ModuleType("alembic")
    module.op = Operations()
    monkeypatch.setitem(sys.modules, "alembic", module)
    path = Path(__file__).parents[2] / "migrations/versions/0001_initial.py"
    spec = importlib.util.spec_from_file_location("initial_migration_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.upgrade()
    path = path.with_name("0002_upload_dedup.py")
    spec = importlib.util.spec_from_file_location("upload_migration_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.upgrade()

    path = path.with_name("0003_sentence_windows.py")
    spec = importlib.util.spec_from_file_location("sentence_migration_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.upgrade()
    path = path.with_name("0004_message_turns.py")
    spec = importlib.util.spec_from_file_location("message_turns_migration_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.upgrade()

    assert set(metadata.tables) == set(Base.metadata.tables)
    for name, table in metadata.tables.items():
        expected = Base.metadata.tables[name]
        assert set(table.c.keys()) == set(expected.c.keys())
        for column in table.c:
            assert isinstance(column, Column)
            assert column.nullable == expected.c[column.name].nullable
            assert str(column.type) == str(expected.c[column.name].type)
            if isinstance(column.type, mysql.DATETIME):
                assert column.type.fsp == expected.c[column.name].type.fsp
        assert {idx.name for idx in table.indexes} == {idx.name for idx in expected.indexes}
        assert str(CreateTable(table).compile(dialect=mysql.dialect()))
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    engine.dispose()
