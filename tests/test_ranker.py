from datetime import datetime, timezone

from ainewsagent.domain.models import Item, Source
from ainewsagent.services.ranker import dedupe_items, rank_items


def make_item(title: str, url: str) -> Item:
    return Item(
        id=url,
        source=Source.ARXIV,
        title=title,
        url=url,
        text="large language model agent reasoning",
        published_at=datetime.now(timezone.utc),
        categories=["cs.AI"],
    )


def test_dedupe_items_by_url():
    item = make_item("Agent Paper", "https://example.com/a")

    assert dedupe_items([item, item]) == [item]


def test_rank_items_limits_results():
    items = [make_item(f"Agent Paper {index}", f"https://example.com/{index}") for index in range(5)]

    assert len(rank_items(items, 3)) == 3
