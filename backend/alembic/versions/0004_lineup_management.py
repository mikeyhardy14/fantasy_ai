"""AI Management tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "lineup_management" not in tables:
        op.create_table(
            "lineup_management",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("league_id", sa.Uuid(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "league_id", name="uq_lineup_management_league"),
        )
        op.create_index("ix_lineup_management_user_id", "lineup_management", ["user_id"])
        op.create_index("ix_lineup_management_league_id", "lineup_management", ["league_id"])


def downgrade() -> None:
    op.drop_table("lineup_management")
