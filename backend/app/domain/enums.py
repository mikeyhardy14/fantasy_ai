from enum import StrEnum


class Provider(StrEnum):
    SLEEPER = "sleeper"
    YAHOO = "yahoo"
    ESPN = "espn"
    NFL = "nfl"
    DEMO = "demo"


class SyncStatus(StrEnum):
    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    ERROR = "error"


class RecommendationType(StrEnum):
    START_SIT = "START_SIT"
    ADD_PLAYER = "ADD_PLAYER"
    DROP_PLAYER = "DROP_PLAYER"
    WAIVER_TARGET = "WAIVER_TARGET"
    TRADE_TARGET = "TRADE_TARGET"
    INJURY_ALERT = "INJURY_ALERT"
    BYE_WEEK = "BYE_WEEK"
    ROSTER_WEAKNESS = "ROSTER_WEAKNESS"


class Priority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TransactionType(StrEnum):
    WAIVER = "waiver"
    FREE_AGENT = "free_agent"
    TRADE = "trade"
    COMMISSIONER = "commissioner"
    UNKNOWN = "unknown"


# Fantasy-relevant positions we track. IDP positions are kept but not analysed.
OFFENSE_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
IDP_POSITIONS = ("DL", "LB", "DB")
FANTASY_POSITIONS = OFFENSE_POSITIONS + IDP_POSITIONS

# Roster slot -> eligible positions. Anything not listed is treated as exact match.
SLOT_ELIGIBILITY: dict[str, tuple[str, ...]] = {
    "FLEX": ("RB", "WR", "TE"),
    "WRRB_FLEX": ("RB", "WR"),
    "REC_FLEX": ("WR", "TE"),
    "SUPER_FLEX": ("QB", "RB", "WR", "TE"),
    "IDP_FLEX": ("DL", "LB", "DB"),
    "DEF": ("DEF",),
    "DST": ("DEF",),
    "D/ST": ("DEF",),
    "K": ("K",),
}

NON_LINEUP_SLOTS = ("BN", "IR", "TAXI")

INJURY_SEVERITY: dict[str, int] = {
    "IR": 4,
    "Out": 4,
    "O": 4,
    "PUP": 4,
    "Sus": 4,
    "NA": 3,
    "Doubtful": 3,
    "D": 3,
    "Questionable": 2,
    "Q": 2,
    "Probable": 1,
}
