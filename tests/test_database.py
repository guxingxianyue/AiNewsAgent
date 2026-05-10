from datetime import datetime, timezone

from ainewsagent.domain.models import Item, Source
from ainewsagent.domain.models import ScoredItem
from ainewsagent.infrastructure.database import AgentDatabase


def test_database_saves_and_reads_briefing(tmp_path):
    db = AgentDatabase(tmp_path / "ainewsagent.db")
    item = Item(
        id="paper-1",
        source=Source.ARXIV,
        title="Agent Paper",
        url="https://arxiv.org/abs/1",
        text="abstract",
        published_at=datetime.now(timezone.utc),
        authors=["Ada"],
        categories=["cs.AI"],
    )

    db.save_run(
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        status="completed",
        report_path="reports/2026-05-06.md",
        date="2026-05-06",
        content="# briefing",
        scored_items=[ScoredItem(item=item, rule_score=10, llm_score=8, topic="智能体", reason="重要进展")],
        failures=[],
    )

    briefing = db.latest_briefing()

    assert briefing is not None
    assert briefing.date == "2026-05-06"
    record = db.items_for_briefing(briefing.id)[0]
    assert record.item.title == "Agent Paper"
    assert record.topic == "智能体"
    assert record.importance == "值得扫读"
    assert db.topic_trends()[0].topic == "智能体"
    assert db.search_briefing_items(query="Agent")[0].item.id == "paper-1"
    assert db.search_briefing_items(source="arxiv")[0].item.id == "paper-1"
    assert db.search_briefing_items(topic="智能体")[0].item.id == "paper-1"
    assert db.filter_options()["topics"] == ["智能体"]
