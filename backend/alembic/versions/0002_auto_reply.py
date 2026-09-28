"""auto reply settings

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "auto_reply_settings" not in tables:
        op.create_table(
            "auto_reply_settings",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("league_id", sa.Uuid(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "league_id", name="uq_auto_reply_league"),
        )
        op.create_index("ix_auto_reply_settings_user_id", "auto_reply_settings", ["user_id"])
        op.create_index("ix_auto_reply_settings_league_id", "auto_reply_settings", ["league_id"])
    if "auto_reply_targets" not in tables:
        op.create_table(
            "auto_reply_targets",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "setting_id",
                sa.Uuid(),
                sa.ForeignKey("auto_reply_settings.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sleeper_user_id", sa.String(128), nullable=False),
            sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_message_id", sa.String(64)),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("setting_id", "sleeper_user_id", name="uq_auto_reply_person"),
        )
        op.create_index("ix_auto_reply_targets_setting_id", "auto_reply_targets", ["setting_id"])


def downgrade() -> None:
    op.drop_table("auto_reply_targets")
    op.drop_table("auto_reply_settings")
