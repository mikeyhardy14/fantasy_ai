from pydantic import BaseModel, Field

from app.domain.enums import Priority, RecommendationType


class Recommendation(BaseModel):
    """An advisory recommendation. Never executed automatically."""

    type: RecommendationType
    priority: Priority
    title: str
    reason: str
    players: list[str] = Field(default_factory=list, description="Internal player ids")
    player_names: list[str] = Field(default_factory=list)
    position: str | None = None
    data: dict = Field(default_factory=dict)

    @property
    def priority_rank(self) -> int:
        return {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}[self.priority]
