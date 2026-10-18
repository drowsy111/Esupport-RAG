"""Link each user/assistant message pair and preserve timestamp precision."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("turn_id", sa.String(36), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column(
            "conversations", "created_at",
            existing_type=sa.DateTime(), type_=mysql.DATETIME(fsp=6),
            existing_nullable=False,
        )
        op.alter_column(
            "messages", "created_at",
            existing_type=sa.DateTime(), type_=mysql.DATETIME(fsp=6),
            existing_nullable=False,
        )
    op.create_index(
        "ix_messages_conversation_created_at", "messages", ["conversation_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_messages_conversation_created_at", table_name="messages")
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column(
            "messages", "created_at",
            existing_type=mysql.DATETIME(fsp=6), type_=sa.DateTime(),
            existing_nullable=False,
        )
        op.alter_column(
            "conversations", "created_at",
            existing_type=mysql.DATETIME(fsp=6), type_=sa.DateTime(),
            existing_nullable=False,
        )
    op.drop_column("messages", "turn_id")
