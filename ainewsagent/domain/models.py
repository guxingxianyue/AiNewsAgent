from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Source(str, Enum):
    X = "x"
    ARXIV = "arxiv"


@dataclass(frozen=True)
class Item:
    id: str
    source: Source
    title: str
    url: str
    text: str
    published_at: datetime
    authors: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    metrics: dict[str, int] = field(default_factory=dict)

    @property
    def stable_key(self) -> str:
        return self.url or self.id

    def age_hours(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        published = self.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        return max((now - published).total_seconds() / 3600, 0.0)


@dataclass(frozen=True)
class ScoredItem:
    item: Item
    rule_score: float
    llm_score: float
    topic: str
    reason: str
    importance: str = "值得扫读"
    audience: str = "技术读者"
    tags: list[str] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        return self.rule_score + self.llm_score
