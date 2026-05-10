from datetime import datetime, timezone

from ainewsagent.domain.models import Item, Source
from ainewsagent.services.report import render_fallback_briefing


def test_render_fallback_briefing_has_links():
    item = Item(
        id="1",
        source=Source.ARXIV,
        title="Reasoning Agents",
        url="https://arxiv.org/abs/1",
        text="abstract",
        published_at=datetime.now(timezone.utc),
    )

    report = render_fallback_briefing([item], [])

    assert "# AI 前沿晨报" in report
    assert "https://arxiv.org/abs/1" in report
