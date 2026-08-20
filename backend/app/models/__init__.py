from datetime import date, datetime
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    role: Mapped[str] = mapped_column(Enum("tenant", "host", "admin", "pending", name="user_role"), default="tenant")
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
    avatar_asset_id: Mapped[UUID | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[UUID | None] = mapped_column(ForeignKey("auth_sessions.id", ondelete="SET NULL"))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_hash: Mapped[str | None] = mapped_column(String(64))


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MailOutbox(Base):
    __tablename__ = "mail_outbox"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    recipient: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(64), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Listing(Timestamped, Base):
    __tablename__ = "listings"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    city: Mapped[str] = mapped_column(String(120))
    area: Mapped[str] = mapped_column(String(120), index=True)
    street: Mapped[str] = mapped_column(String(160), default="")
    postcode: Mapped[str] = mapped_column(String(32), default="")
    approximate_address: Mapped[str] = mapped_column(String(240))
    rental_mode: Mapped[str] = mapped_column(Enum("long", "holiday", name="rental_mode"), index=True)
    monthly_price: Mapped[int | None] = mapped_column(Integer)
    nightly_price: Mapped[int | None] = mapped_column(Integer)
    weekly_price: Mapped[int | None] = mapped_column(Integer)
    room_type: Mapped[str] = mapped_column(String(64), default="Habitación individual")
    available_from: Mapped[date | None] = mapped_column(Date)
    available_until: Mapped[date | None] = mapped_column(Date)
    minimum_stay_months: Mapped[int | None] = mapped_column(Integer, default=0)
    minimum_nights: Mapped[int | None] = mapped_column(Integer)
    deposit_amount: Mapped[int | None] = mapped_column(Integer, default=0)
    deposit_text: Mapped[str | None] = mapped_column(String(240))
    bills_included: Mapped[bool | None] = mapped_column(Boolean, default=False)
    bills_text: Mapped[str | None] = mapped_column(String(240))
    bathroom: Mapped[str | None] = mapped_column(String(64), default="Baño compartido")
    kitchen: Mapped[str | None] = mapped_column(String(64), default="Cocina compartida")
    furnished: Mapped[bool | None] = mapped_column(Boolean, default=True)
    room_size_m2: Mapped[int | None] = mapped_column(Integer, default=1)
    bedroom_count: Mapped[int | None] = mapped_column(Integer)
    current_residents: Mapped[int] = mapped_column(Integer, default=0)
    room_capacity: Mapped[int | None] = mapped_column(Integer, default=1)
    shower: Mapped[str] = mapped_column(String(64), default="Ducha compartida")
    tenant_requirement: Mapped[str | None] = mapped_column(String(32), default="any")
    smoking_allowed: Mapped[bool | None] = mapped_column(Boolean, default=False)
    pets_allowed: Mapped[bool | None] = mapped_column(Boolean, default=False)
    children_allowed: Mapped[bool | None] = mapped_column(Boolean, default=False)
    empadronamiento_allowed: Mapped[bool | None] = mapped_column(Boolean, default=False)
    restrictions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    amenities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    external_image_urls: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(
        Enum("draft", "pending", "published", "hidden", "closed", "rejected", name="listing_status"),
        default="draft",
        index=True,
    )
    # `location` is deliberately the public, approximate point.  Never use it
    # to store the exact address coordinate returned by a host.
    location: Mapped[str] = mapped_column(Geography("POINT", srid=4326), index=True)
    exact_location: Mapped[str | None] = mapped_column(Geography("POINT", srid=4326))
    description: Mapped[str] = mapped_column(Text, default="")
    home_description: Mapped[str] = mapped_column(Text, default="")
    advertiser_name: Mapped[str | None] = mapped_column(String(160))
    advertiser_type: Mapped[str | None] = mapped_column(String(32), default="Particular")
    source: Mapped[str | None] = mapped_column(String(120))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    closed_reason: Mapped[str | None] = mapped_column(String(32))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    primary_source: Mapped[str | None] = mapped_column(String(64), index=True)
    primary_source_url: Mapped[str | None] = mapped_column(Text)
    source_price_text: Mapped[str | None] = mapped_column(String(120))
    source_price_currency: Mapped[str | None] = mapped_column(String(8))
    source_price_period: Mapped[str | None] = mapped_column(String(16))
    source_price_is_from: Mapped[bool | None] = mapped_column(Boolean)
    external_contact_phone: Mapped[str | None] = mapped_column(String(64))
    external_contact_whatsapp: Mapped[str | None] = mapped_column(String(64))
    external_contact_email: Mapped[str | None] = mapped_column(String(320))
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExternalListingSource(Base):
    __tablename__ = "external_listing_sources"
    __table_args__ = (
        UniqueConstraint("source_name", "external_id", name="uq_external_listing_source_external_id"),
        UniqueConstraint("source_url", name="uq_external_listing_source_url"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(Text)
    canonical_listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    normalized_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    source_price_text: Mapped[str | None] = mapped_column(String(120))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_missing_runs: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_unknown_state_runs: Mapped[int] = mapped_column(Integer, default=0)
    current_status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    removed_reason: Mapped[str | None] = mapped_column(String(32))
    last_state_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_state_check_result: Mapped[str | None] = mapped_column(String(32))


class ExternalImportRun(Base):
    __tablename__ = "external_import_runs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    source_name: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str] = mapped_column(String(32), default="running")
    counters: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text)
    challenge_type: Mapped[str | None] = mapped_column(String(64))
    http_status: Mapped[int | None] = mapped_column(Integer)
    final_url: Mapped[str | None] = mapped_column(Text)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    diagnostic_paths: Mapped[dict] = mapped_column(JSONB, default=dict)
    discovery_complete: Mapped[bool | None] = mapped_column(Boolean)
    discovery_pages: Mapped[int | None] = mapped_column(Integer)
    discovery_failed_pages: Mapped[list[str]] = mapped_column(JSONB, default=list)


class ExternalWorkerState(Base):
    __tablename__ = "external_worker_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    health: Mapped[str] = mapped_column(String(16), default="healthy", index=True)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_run_id: Mapped[str | None] = mapped_column(String(64))


class MailWorkerState(Base):
    __tablename__ = "mail_worker_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    health: Mapped[str] = mapped_column(String(16), default="healthy", index=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class CatalogState(Base):
    __tablename__ = "catalog_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


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


class ListingView(Base):
    __tablename__ = "listing_views"
    __table_args__ = (UniqueConstraint("listing_id", "viewer_key", "view_date", name="uq_listing_views_daily"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    viewer_key: Mapped[str] = mapped_column(String(64))
    view_date: Mapped[date] = mapped_column(Date, index=True)
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
    perceptual_hash: Mapped[str | None] = mapped_column(String(16), index=True)
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


# Alembic imports this package to build Base.metadata. Keep every mapped model
# module registered here so autogeneration can never mistake application tables
# for orphaned schema objects.
from .moderation import (  # noqa: F401
    AdminAccess,
    AdminNote,
    ListingPromotion,
    ListingRestriction,
    ModerationNotice,
    UserReportTarget,
    UserRestriction,
)
from .room_details import ListingRoomDetails  # noqa: F401
from .storage_deletion import StorageDeletionJob  # noqa: F401
