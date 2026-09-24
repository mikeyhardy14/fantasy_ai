"""Consensus lines and vig-free win probabilities.

Implied points use the home spread (negative when the home team is favored):

    home = (total - home_spread) / 2
    away = (total + home_spread) / 2

When more than one book posts a number, the spreads and totals are averaged.
A moneyline becomes a probability, then the two sides are scaled so they sum to 1.
"""

from dataclasses import dataclass

from app.nfl_data.vegas import implied_team_points


@dataclass
class BookPrice:
    name: str
    home_spread: float | None = None
    total: float | None = None
    home_ml: float | None = None
    away_ml: float | None = None


@dataclass
class Consensus:
    home_spread: float | None
    total: float | None
    home_implied: float | None
    away_implied: float | None
    home_win_probability: float | None
    books: list[str]
    book_count: int


def parse_american(raw: object) -> float | None:
    """American odds. Positive is the underdog. EVEN is +100."""
    if raw is None or raw == "":
        return None
    text = str(raw).strip().upper().replace("−", "-").replace("+", "")
    if text in {"EVEN", "PK", "PICK"}:
        return 100.0
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    return value


def american_probability(ml: float) -> float | None:
    """Implied probability before the vig is removed."""
    if ml == 0:
        return None
    if ml > 0:
        return 100 / (ml + 100)
    return -ml / (-ml + 100)


def fair_home_probability(home_ml: float, away_ml: float) -> float | None:
    """Home win probability after the two moneylines are scaled to sum to 1."""
    home = american_probability(home_ml)
    away = american_probability(away_ml)
    if home is None or away is None:
        return None
    total = home + away
    if total <= 0:
        return None
    return home / total


def consensus(books: list[BookPrice]) -> Consensus:
    """Average every book that posted a spread or a total. Devig each moneyline pair, then average those."""
    spreads: list[float] = []
    totals: list[float] = []
    probs: list[float] = []
    names: list[str] = []
    for book in books:
        if book.home_spread is None and book.total is None and book.home_ml is None:
            continue
        if book.name not in names:
            names.append(book.name)
        if book.home_spread is not None:
            spreads.append(book.home_spread)
        if book.total is not None:
            totals.append(book.total)
        if book.home_ml is not None and book.away_ml is not None:
            fair = fair_home_probability(book.home_ml, book.away_ml)
            if fair is not None:
                probs.append(fair)
    home_spread = sum(spreads) / len(spreads) if spreads else None
    total = sum(totals) / len(totals) if totals else None
    home_implied = (
        implied_team_points(total, home_spread) if total is not None and home_spread is not None else None
    )
    away_implied = (
        implied_team_points(total, -home_spread) if total is not None and home_spread is not None else None
    )
    win = sum(probs) / len(probs) if probs else None
    return Consensus(
        home_spread=home_spread,
        total=total,
        home_implied=home_implied,
        away_implied=away_implied,
        home_win_probability=win,
        books=names,
        book_count=len(spreads),
    )
