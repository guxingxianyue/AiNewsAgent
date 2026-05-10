from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ainewsagent.domain.models import Item, Source


def render_fallback_briefing(items: list[Item], failures: list[str]) -> str:
    lines = [
        "# AI 前沿晨报",
        "",
        "## 今日重点",
    ]
    if not items:
        lines.append("- 今天没有采集到可用候选内容。")
    for item in items[:5]:
        lines.append(f"- [{item.title}]({item.url})")

    lines.extend(["", "## X 热点"])
    _append_source(lines, items, Source.X)
    lines.extend(["", "## arXiv 论文精选"])
    _append_source(lines, items, Source.ARXIV)
    lines.extend(["", "## 交叉趋势/观察", "- 未调用大模型，当前为规则生成简报。"])
    if failures:
        lines.extend(["", "## 采集问题"])
        lines.extend(f"- {failure}" for failure in failures)
    lines.extend(["", "## 原始链接列表"])
    lines.extend(f"- {item.url}" for item in items)
    return "\n".join(lines).strip() + "\n"


def write_report(content: str, output_dir: Path, now: datetime) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{now.date().isoformat()}.md"
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def _append_source(lines: list[str], items: list[Item], source: Source) -> None:
    source_items = [item for item in items if item.source == source]
    if not source_items:
        lines.append("- 暂无。")
        return
    for item in source_items:
        authors = ", ".join(item.authors[:3])
        lines.append(f"- [{item.title}]({item.url})" + (f" - {authors}" if authors else ""))
