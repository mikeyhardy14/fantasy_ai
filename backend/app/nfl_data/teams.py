"""NFL abbreviation normalization.

Sleeper uses WAS and JAX. ESPN's scoreboard uses WSH and JAX. Schedule lookups
and logo URLs go through these so either code finds the same game.
"""

_TO_APP = {"WSH": "WAS", "JAC": "JAX"}
_TO_ESPN = {"WAS": "WSH", "JAC": "JAX"}


def app_team(abbr: str | None) -> str:
    team = (abbr or "").upper()
    return _TO_APP.get(team, team)


def espn_team(abbr: str | None) -> str:
    team = (abbr or "").upper()
    return _TO_ESPN.get(team, team)
