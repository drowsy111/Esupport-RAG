"""Initial frozen schema. Subsequent model changes require new migrations."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def identity():
    return sa.Column("id", sa.String(36), primary_key=True)


def tenant():
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False)


def upgrade():
    op.create_table("tenants", identity(), sa.Column("name", sa.String(120), nullable=False, unique=True))
    op.create_table(
        "users", identity(), tenant(),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.UniqueConstraint("tenant_id", "username"),
    )
    op.create_table("knowledge_bases", identity(), tenant(),
                    sa.Column("name", sa.String(150), nullable=False))
    op.create_table(
        "kb_members", identity(), tenant(),
        sa.Column("knowledge_base_id", sa.String(36), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("knowledge_base_id", "user_id"),
    )
    op.create_table(
        "documents", identity(), tenant(),
        sa.Column("knowledge_base_id", sa.String(36), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "document_versions", identity(), tenant(),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("publication_status", sa.String(20), nullable=False),
        sa.Column("product_id", sa.String(100), nullable=False),
        sa.Column("product_version", sa.String(50), nullable=False),
        sa.Column("deployment_mode", sa.String(50), nullable=False),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "revision"),
    )
    op.create_table(
        "chunks", sa.Column("id", sa.String(64), primary_key=True), tenant(),
        sa.Column("knowledge_base_id", sa.String(36), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("title_path", sa.String(1000), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("anchor", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("version_id", "chunk_index"),
    )
    op.create_table(
        "ingestion_jobs", identity(), tenant(),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("document_versions.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(25), nullable=False),
        sa.Column("stage", sa.String(25), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "conversations", identity(), tenant(),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "messages", identity(), tenant(),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    indexes = {
        "users": ["tenant_id"], "knowledge_bases": ["tenant_id"], "kb_members": ["tenant_id"],
        "documents": ["tenant_id", "knowledge_base_id"],
        "document_versions": ["tenant_id", "document_id"],
        "chunks": ["tenant_id", "knowledge_base_id", "document_id", "version_id"],
        "ingestion_jobs": ["tenant_id"], "conversations": ["tenant_id"],
        "messages": ["tenant_id", "conversation_id"],
    }
    for table, columns in indexes.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in ["messages", "conversations", "ingestion_jobs", "chunks",
                  "document_versions", "documents", "kb_members", "knowledge_bases", "users", "tenants"]:
        op.drop_table(table)

