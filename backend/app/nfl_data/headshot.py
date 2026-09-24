"""Player face URLs. ESPN headshot when we have an espn id, otherwise the
Sleeper thumbnail that already exists for every synced player. Defenses use
the team logo.
"""

from app.models import Player
from app.nfl_data.teams import espn_team
from app.nfl_data.vegas import normalize_position


def headshot_url(player: Player) -> str | None:
    extra = player.extra or {}
    espn_id = extra.get("espn_id")
    if espn_id:
        return f"https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png"
    position = normalize_position(player.position)
    if position == "DEF" and player.nfl_team:
        return f"https://a.espncdn.com/i/teamlogos/nfl/500/{espn_team(player.nfl_team).lower()}.png"
    sleeper_id = player.external_id_for("sleeper")
    if sleeper_id and str(sleeper_id).isdigit():
        return f"https://sleepercdn.com/content/nfl/players/thumb/{sleeper_id}.jpg"
    return None
