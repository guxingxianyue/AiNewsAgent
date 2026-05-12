from pathlib import Path

from ainewsagent.application.pipeline import collect_candidates, run_once
from ainewsagent.domain.models import Item, ScoredItem, Source
from ainewsagent.infrastructure.config import Settings


class FakeLLM:
    def __init__(self, expected_failures=None):
        self.expected_failures = expected_failures

    def create_briefing(self, items, failures):
        assert len(items) == 1
        if self.expected_failures is not None:
            assert failures == self.expected_failures
        return "# fake briefing\n\n- done"

    def score_items(self, items, max_items, **kwargs):
        assert len(items) >= 1
        return [
            ScoredItem(item=item, rule_score=10.0, llm_score=8.0, topic="智能体", reason="测试入选")
            for item in items[:max_items]
        ]

    def create_briefing_from_scored(self, scored_items, failures):
        assert len(scored_items) == 1
        if self.expected_failures is not None:
            assert failures == self.expected_failures
        return "# fake briefing\n\n- done"


def test_run_once_writes_report_with_arxiv(monkeypatch, tmp_path):
    item = Item(
        id="paper-1",
        source=Source.ARXIV,
        title="Agent reasoning paper",
        url="https://arxiv.org/abs/1",
        text="large language model agent reasoning",
        published_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        categories=["cs.AI"],
    )

    monkeypatch.setattr("ainewsagent.application.pipeline.fetch_recent_papers", lambda *args, **kwargs: [item])

    settings = Settings(
        output_dir=tmp_path / "reports",
        data_dir=tmp_path / "data",
    )

    path, failures = run_once(settings, FakeLLM(expected_failures=[]))

    assert failures == []
    assert Path(path).read_text(encoding="utf-8").startswith("# fake briefing")
    assert (tmp_path / "data" / "seen.json").exists()


def test_collect_candidates_can_include_seen(monkeypatch, tmp_path):
    item = Item(
        id="paper-1",
        source=Source.ARXIV,
        title="Agent reasoning paper",
        url="https://arxiv.org/abs/1",
        text="large language model agent reasoning",
        published_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        categories=["cs.AI"],
    )
    monkeypatch.setattr("ainewsagent.application.pipeline.fetch_recent_papers", lambda *args, **kwargs: [item])
    settings = Settings(output_dir=tmp_path / "reports", data_dir=tmp_path / "data")

    first, _ = collect_candidates(settings)
    run_once(settings, FakeLLM())
    second, _ = collect_candidates(settings)
    third, _ = collect_candidates(settings, include_seen=True)

    assert first == [item]
    assert second == []
    assert third == [item]
