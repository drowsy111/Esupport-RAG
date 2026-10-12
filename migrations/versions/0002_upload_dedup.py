"""Add upload content claims and idempotency receipts without deleting history."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "upload_claims",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("document_versions.id"), nullable=False),
    )
    op.create_table(
        "upload_receipts",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("document_versions.id"), nullable=False),
    )


def downgrade():
    op.drop_table("upload_receipts")
    op.drop_table("upload_claims")
