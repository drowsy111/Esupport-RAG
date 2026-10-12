from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UploadClaim(Base):
    """Unique, tenant/KB-scoped content identity; historical files stay untouched."""
    __tablename__ = "upload_claims"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))


class UploadReceipt(Base):
    """Actor/KB-scoped idempotency result, retained for the document lifetime."""
    __tablename__ = "upload_receipts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
