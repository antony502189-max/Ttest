"""Registered immutable AI intent child, independent of conversation lifetime."""
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKeyConstraint, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class AiSavedSearch(Base):
    __tablename__ = "ai_saved_searches"
    __table_args__ = (
        ForeignKeyConstraint(["saved_search_id", "matcher"], ["saved_searches.id", "saved_searches.matcher"],
                             ondelete="CASCADE", name="fk_ai_saved_search_matcher"),
        CheckConstraint("matcher = 'ai.v1'", name="ck_ai_saved_matcher"),
        CheckConstraint("revision > 0", name="ck_ai_saved_revision"),
        CheckConstraint("schema_version = 'ai-search.v1' AND taxonomy_version = 'rental.v1'", name="ck_ai_saved_versions"),
        CheckConstraint("intent_hash ~ '^[0-9a-f]{64}$'", name="ck_ai_saved_hash"),
        CheckConstraint("jsonb_typeof(criteria) = 'object' AND octet_length(criteria::text) <= 65536",
                        name="ck_ai_saved_criteria"),
    )
    saved_search_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    matcher: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean)
    schema_version: Mapped[str] = mapped_column(String(32))
    taxonomy_version: Mapped[str] = mapped_column(String(32))
    criteria: Mapped[dict] = mapped_column(JSONB)
    intent_hash: Mapped[str] = mapped_column(String(64))
