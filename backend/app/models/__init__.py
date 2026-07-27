from datetime import datetime
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Timestamped, Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(512))
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(Enum("tenant", "host", "admin", name="user_role"), default="tenant")
    phone: Mapped[str] = mapped_column(String(64), default="")
    whatsapp: Mapped[str] = mapped_column(String(64), default="")
    telegram: Mapped[str] = mapped_column(String(64), default="")
    about: Mapped[str] = mapped_column(Text, default="")
    initials: Mapped[str] = mapped_column(String(8), default="")
    show_phone: Mapped[bool] = mapped_column(Boolean, default=False)
    show_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_contact_form: Mapped[bool] = mapped_column(Boolean, default=True)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Listing(Timestamped, Base):
    __tablename__ = "listings"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    city: Mapped[str] = mapped_column(String(120))
    area: Mapped[str] = mapped_column(String(120), index=True)
    approximate_address: Mapped[str] = mapped_column(String(240))
    rental_mode: Mapped[str] = mapped_column(Enum("long", "holiday", name="rental_mode"), index=True)
    monthly_price: Mapped[int | None] = mapped_column(Integer)
    nightly_price: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        Enum("draft", "pending", "published", "hidden", "closed", "rejected", name="listing_status"),
        default="draft",
        index=True,
    )
    location: Mapped[str] = mapped_column(Geography("POINT", srid=4326), index=True)
    description: Mapped[str] = mapped_column(Text, default="")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_favorites_user_listing"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiscardedListing(Base):
    __tablename__ = "discarded_listings"
    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_discarded_user_listing"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavedSearch(Timestamped, Base):
    __tablename__ = "saved_searches"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    query: Mapped[str] = mapped_column(String(240), default="")
    rental_mode: Mapped[str] = mapped_column(Enum("long", "holiday", name="rental_mode"))
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    polygon: Mapped[list] = mapped_column(JSONB, default=list)
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class MessageThread(Timestamped, Base):
    __tablename__ = "message_threads"
    __table_args__ = (UniqueConstraint("listing_id", "tenant_id", name="uq_thread_listing_tenant"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    host_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    thread_id: Mapped[UUID] = mapped_column(ForeignKey("message_threads.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    public_reference: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    reporter_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    reason: Mapped[str] = mapped_column(String(120))
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        Enum("open", "in_review", "resolved", "rejected", name="report_status"), default="open", index=True
    )
    handled_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ListingStatusHistory(Base):
    __tablename__ = "listing_status_history"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    changed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(Enum("listing_image", "avatar", name="media_kind"), default="listing_image")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ListingImage(Base):
    __tablename__ = "listing_images"
    __table_args__ = (UniqueConstraint("listing_id", "sort_order", name="uq_listing_images_sort_order"),)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True)
    media_asset_id: Mapped[UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchHistory(Base):
    __tablename__ = "search_history"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    normalized_query: Mapped[str] = mapped_column(String(240), index=True)
    searched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
