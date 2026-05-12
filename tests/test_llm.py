from ainewsagent.domain.models import Item, Source
from ainewsagent.services.llm import build_prompt, build_scoring_prompt


def test_build_prompt_contains_required_sections():
    item = Item(
        id="1",
        source=Source.ARXIV,
        title="New AI paper",
        url="https://arxiv.org/abs/1",
        text="A notable model paper.",
        published_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        authors=["Ada Lovelace"],
    )

    prompt = build_prompt([item], ["arXiv warning"])

    assert "今日重点" in prompt
    assert "arXiv warning" in prompt
    assert "https://arxiv.org/abs/1" in prompt


def test_build_scoring_prompt_contains_preferences():
    item = Item(
        id="1",
        source=Source.ARXIV,
        title="Agent benchmark",
        url="https://arxiv.org/abs/1",
        text="agent benchmark",
        published_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )

    prompt = build_scoring_prompt(
        [item],
        5,
        interests=["AI Agent"],
        avoid_topics=["纯营销"],
        reading_level="technical",
    )

    assert "用户兴趣：AI Agent" in prompt
    assert "避免主题：纯营销" in prompt
    assert "importance" in prompt
