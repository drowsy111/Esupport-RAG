"""Persist source positions for sentence windows; legacy chunks remain unchanged."""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chunks", sa.Column("structure", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("chunks", "structure")
