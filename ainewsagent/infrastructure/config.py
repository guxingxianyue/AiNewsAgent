from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


DEFAULT_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO", "cs.HC", "cs.SE"]
DEFAULT_INTERESTS = ["AI Agent", "LLM 推理", "多模态", "AI 编程", "开源模型"]


@dataclass(frozen=True)
class Settings:
    x_list_url: str = ""
    x_accounts: list[str] = field(default_factory=list)
    arxiv_categories: list[str] = field(default_factory=lambda: DEFAULT_CATEGORIES.copy())
    max_items: int = 15
    timezone: str = "Asia/Shanghai"
    output_dir: Path = Path("reports")
    data_dir: Path = Path("data")
    x_profile_dir: Path = Path(".ainewsagent/x-profile")
    x_browser_channel: str = ""
    x_max_posts: int = 40
    arxiv_max_results: int = 80
    interests: list[str] = field(default_factory=lambda: DEFAULT_INTERESTS.copy())
    avoid_topics: list[str] = field(default_factory=list)
    reading_level: str = "technical"

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "ainewsagent.db"


def load_settings(path: Path = Path("config.yaml")) -> Settings:
    if not path.exists():
        return Settings()

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Settings(
        x_list_url=str(data.get("x_list_url") or ""),
        x_accounts=[str(account).lstrip("@") for account in data.get("x_accounts", []) if account],
        arxiv_categories=list(data.get("arxiv_categories") or DEFAULT_CATEGORIES),
        max_items=int(data.get("max_items", 15)),
        timezone=str(data.get("timezone") or "Asia/Shanghai"),
        output_dir=Path(data.get("output_dir") or "reports"),
        data_dir=Path(data.get("data_dir") or "data"),
        x_profile_dir=Path(data.get("x_profile_dir") or ".ainewsagent/x-profile"),
        x_browser_channel=str(data.get("x_browser_channel") or ""),
        x_max_posts=int(data.get("x_max_posts", 40)),
        arxiv_max_results=int(data.get("arxiv_max_results", 80)),
        interests=[str(topic) for topic in data.get("interests", DEFAULT_INTERESTS)],
        avoid_topics=[str(topic) for topic in data.get("avoid_topics", [])],
        reading_level=str(data.get("reading_level") or "technical"),
    )
