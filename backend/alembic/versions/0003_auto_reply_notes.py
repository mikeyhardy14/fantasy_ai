"""auto reply voice notes

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in sa.inspect(bind).get_columns("auto_reply_targets")}
    if "note" not in columns:
        op.add_column("auto_reply_targets", sa.Column("note", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("auto_reply_targets", "note")
