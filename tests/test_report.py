from datetime import datetime, timezone

from ainewsagent.domain.models import Item, Source
from ainewsagent.services.report import render_fallback_briefing, with_report_metadata


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


def test_with_report_metadata_inserts_header_block():
    content = "# AI 前沿晨报\n\n## 今日重点\n- x"
    report = with_report_metadata(
        content,
        generated_at=datetime.now(timezone.utc),
        timezone="Asia/Shanghai",
        sources=["arXiv"],
        candidate_count=8,
        selected_count=3,
        failures=["arXiv timeout"],
        selection_scope="scope",
    )
    assert "## 报告元信息" in report
    assert "候选数量/入选数量：8/3" in report
    assert "## 今日重点" in report
