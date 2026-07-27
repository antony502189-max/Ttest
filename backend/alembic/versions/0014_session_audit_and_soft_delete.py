"""add session audit and user deletion fields"""

from alembic import op
import sqlalchemy as sa

revision = "0014_session_audit"
down_revision = "0013_mail_outbox"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("avatar_asset_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_users_avatar_asset", "users", "media_assets", ["avatar_asset_id"], ["id"], ondelete="SET NULL")
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])
    op.add_column("auth_sessions", sa.Column("replaced_by", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_auth_sessions_replaced_by", "auth_sessions", "auth_sessions", ["replaced_by"], ["id"], ondelete="SET NULL")
    op.add_column("auth_sessions", sa.Column("user_agent", sa.String(512), nullable=True))
    op.add_column("auth_sessions", sa.Column("ip_hash", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("auth_sessions", "ip_hash")
    op.drop_column("auth_sessions", "user_agent")
    op.drop_constraint("fk_auth_sessions_replaced_by", "auth_sessions", type_="foreignkey")
    op.drop_column("auth_sessions", "replaced_by")
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_constraint("fk_users_avatar_asset", "users", type_="foreignkey")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "avatar_asset_id")
