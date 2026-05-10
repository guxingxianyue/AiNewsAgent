from __future__ import annotations

import hashlib
from difflib import SequenceMatcher

from ainewsagent.domain.models import Item, Source

KEYWORDS = {
    "agent": 5,
    "agents": 5,
    "llm": 5,
    "large language model": 5,
    "reasoning": 4,
    "multimodal": 4,
    "robotics": 4,
    "alignment": 4,
    "inference": 3,
    "training": 3,
    "benchmark": 3,
    "computer vision": 3,
    "diffusion": 3,
    "生成式": 4,
    "大模型": 5,
    "推理": 4,
    "智能体": 5,
}


def dedupe_items(items: list[Item], *, similarity_threshold: float = 0.92) -> list[Item]:
    unique: list[Item] = []
    seen_keys: set[str] = set()
    seen_hashes: set[str] = set()
    for item in items:
        content_hash = _content_hash(item)
        if item.stable_key in seen_keys or content_hash in seen_hashes:
            continue
        if any(_similar(item.title, existing.title) >= similarity_threshold for existing in unique):
            continue
        unique.append(item)
        seen_keys.add(item.stable_key)
        seen_hashes.add(content_hash)
    return unique


def rank_items(items: list[Item], max_items: int) -> list[Item]:
    ranked = sorted(items, key=score_item, reverse=True)
    return ranked[:max_items]


def score_item(item: Item) -> float:
    text = f"{item.title} {item.text}".lower()
    keyword_score = sum(weight for keyword, weight in KEYWORDS.items() if keyword in text)
    freshness_score = max(0.0, 20.0 - item.age_hours() / 4.0)
    source_score = 4.0 if item.source == Source.ARXIV else 3.0
    metric_score = min(sum(item.metrics.values()) / 1000.0, 5.0) if item.metrics else 0.0
    category_score = 3.0 if any(category in {"cs.AI", "cs.LG", "cs.CL", "cs.CV"} for category in item.categories) else 0.0
    return keyword_score + freshness_score + source_score + metric_score + category_score


def _content_hash(item: Item) -> str:
    normalized = " ".join(f"{item.title} {item.text}".lower().split())
    return hashlib.sha256(normalized[:500].encode("utf-8")).hexdigest()


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(a=a.lower(), b=b.lower()).ratio()
