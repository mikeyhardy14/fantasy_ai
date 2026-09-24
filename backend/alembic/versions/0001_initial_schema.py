"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "fantasy_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_user_id", sa.String(128), nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(128)),
        sa.Column("avatar", sa.String(512)),
        sa.Column("encrypted_credentials", sa.Text()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "provider", "external_user_id", name="uq_account_identity"),
    )
    op.create_index("ix_fantasy_accounts_user_id", "fantasy_accounts", ["user_id"])

    op.create_table(
        "leagues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "fantasy_account_id",
            sa.Uuid(),
            sa.ForeignKey("fantasy_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_league_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("team_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32)),
        sa.Column("avatar", sa.String(512)),
        sa.Column("scoring_settings", sa.JSON(), nullable=False),
        sa.Column("roster_settings", sa.JSON(), nullable=False),
        sa.Column("league_settings", sa.JSON(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("sync_status", sa.String(16), nullable=False, server_default="idle"),
        sa.Column("sync_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("fantasy_account_id", "external_league_id", name="uq_league_identity"),
    )
    op.create_index("ix_leagues_fantasy_account_id", "leagues", ["fantasy_account_id"])

    op.create_table(
        "fantasy_teams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("league_id", sa.Uuid(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_team_id", sa.String(128), nullable=False),
        sa.Column("owner_external_id", sa.String(128)),
        sa.Column("owner_name", sa.String(128)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("avatar", sa.String(512)),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ties", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_for", sa.Float(), nullable=False, server_default="0"),
        sa.Column("points_against", sa.Float(), nullable=False, server_default="0"),
        sa.Column("faab_remaining", sa.Integer()),
        sa.Column("waiver_position", sa.Integer()),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("league_id", "external_team_id", name="uq_team_identity"),
    )
    op.create_index("ix_fantasy_teams_league_id", "fantasy_teams", ["league_id"])
    op.create_index("ix_fantasy_teams_owner_external_id", "fantasy_teams", ["owner_external_id"])

    op.create_table(
        "players",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("first_name", sa.String(80)),
        sa.Column("last_name", sa.String(80)),
        sa.Column("position", sa.String(8)),
        sa.Column("fantasy_positions", sa.JSON(), nullable=False),
        sa.Column("nfl_team", sa.String(8)),
        sa.Column("status", sa.String(32)),
        sa.Column("injury_status", sa.String(32)),
        sa.Column("injury_body_part", sa.String(64)),
        sa.Column("age", sa.Integer()),
        sa.Column("years_exp", sa.Integer()),
        sa.Column("number", sa.Integer()),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_players_name", "players", ["name"])
    op.create_index("ix_players_last_name", "players", ["last_name"])
    op.create_index("ix_players_position", "players", ["position"])
    op.create_index("ix_players_nfl_team", "players", ["nfl_team"])

    op.create_table(
        "player_external_ids",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.UniqueConstraint("provider", "external_id", name="uq_player_external"),
    )
    op.create_index("ix_player_external_ids_player_id", "player_external_ids", ["player_id"])

    op.create_table(
        "roster_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "fantasy_team_id",
            sa.Uuid(),
            sa.ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("player_id", sa.Uuid(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("roster_slot", sa.String(16), nullable=False),
        sa.Column("slot_index", sa.Integer()),
        sa.Column("is_starter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("fantasy_team_id", "player_id", "week", name="uq_roster_entry"),
    )
    op.create_index("ix_roster_entries_fantasy_team_id", "roster_entries", ["fantasy_team_id"])
    op.create_index("ix_roster_entries_player_id", "roster_entries", ["player_id"])

    op.create_table(
        "matchups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("league_id", sa.Uuid(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("external_matchup_id", sa.String(64)),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("fantasy_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opponent_team_id", sa.Uuid(), sa.ForeignKey("fantasy_teams.id", ondelete="SET NULL")),
        sa.Column("points", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_points", sa.Float()),
        sa.Column("player_points", sa.JSON(), nullable=False),
        sa.UniqueConstraint("league_id", "week", "team_id", name="uq_matchup_team"),
    )
    op.create_index("ix_matchups_league_id", "matchups", ["league_id"])
    op.create_index("ix_matchups_week", "matchups", ["week"])
    op.create_index("ix_matchups_team_id", "matchups", ["team_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("league_id", sa.Uuid(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_transaction_id", sa.String(128), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("week", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint("league_id", "external_transaction_id", name="uq_transaction_identity"),
    )
    op.create_index("ix_transactions_league_id", "transactions", ["league_id"])


def downgrade() -> None:
    for table in (
        "transactions",
        "matchups",
        "roster_entries",
        "player_external_ids",
        "players",
        "fantasy_teams",
        "leagues",
        "fantasy_accounts",
        "users",
    ):
        op.drop_table(table)
