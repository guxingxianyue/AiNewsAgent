from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from ainewsagent.infrastructure.config import Settings
from ainewsagent.infrastructure.database import AgentDatabase
from ainewsagent.infrastructure.state import SeenState
from ainewsagent.services.llm import LLMClient
from ainewsagent.services.ranker import dedupe_items, rank_items
from ainewsagent.services.report import render_fallback_briefing, with_report_metadata, write_report
from ainewsagent.sources.arxiv import fetch_recent_papers
from ainewsagent.domain.models import Item, ScoredItem


@dataclass(frozen=True)
class RunResult:
    report_path: str
    failures: list[str]
    status: str


def collect_candidates(settings: Settings, *, include_seen: bool = False, max_items: int | None = None) -> tuple[list[Item], list[str]]:
    failures: list[str] = []
    items: list[Item] = []

    try:
        items.extend(fetch_recent_papers(settings.arxiv_categories, settings.arxiv_max_results))
    except Exception as exc:
        failures.append(f"arXiv fetch failed: {exc}")

    state = SeenState.load(settings.data_dir)
    unique_items = dedupe_items(items)
    if not include_seen:
        unique_items = [item for item in unique_items if not state.is_seen(item)]
    selected = rank_items(unique_items, max_items or settings.max_items)
    return selected, failures


def run_once(
    settings: Settings,
    llm: LLMClient,
    now: datetime | None = None,
    progress: Callable[[str], None] | None = None,
) -> RunResult:
    def tell(message: str) -> None:
        if progress:
            progress(message)

    started_at = datetime.now(settings.zone)
    now = now or started_at
    db = AgentDatabase(settings.database_path)
    existing = db.briefing_by_date(now.date().isoformat())
    if existing:
        failures = [f"重复运行：{now.date().isoformat()} 已存在简报，已跳过。"]
        db.save_error_run(
            started_at=started_at,
            finished_at=datetime.now(settings.zone),
            status="skipped_duplicate",
            failures=failures,
        )
        return RunResult(report_path=existing.report_path, failures=failures, status="skipped_duplicate")

    candidate_limit = max(settings.max_items * 3, settings.max_items)
    tell("Collecting recent arXiv papers...")
    candidates, failures = collect_candidates(settings, max_items=candidate_limit)
    if not candidates:
        failures.append("候选为空：去重/过滤后没有可用论文。")
    tell(f"Collected {len(candidates)} candidate papers. Scoring with Mimo...")
    scored_items, score_warnings = llm.score_items_with_warnings(
        candidates,
        settings.max_items,
        interests=settings.interests,
        avoid_topics=settings.avoid_topics,
        reading_level=settings.reading_level,
    )
    failures.extend(score_warnings)
    if not scored_items and candidates:
        scored_items = [
            ScoredItem(item=item, rule_score=0.0, llm_score=0.0, topic="论文", reason="无模型结果，规则降级输出。")
            for item in candidates[: settings.max_items]
        ]
    selected = [scored.item for scored in scored_items]
    tell(f"Selected {len(scored_items)} papers. Generating briefing...")
    try:
        content = llm.create_briefing_from_scored(scored_items, failures)
    except Exception as exc:
        failures.append(f"LLM 简报生成失败：{exc}")
        content = render_fallback_briefing(selected, failures)
    content = with_report_metadata(
        content,
        generated_at=now,
        timezone=settings.timezone,
        sources=["arXiv"],
        candidate_count=len(candidates),
        selected_count=len(scored_items),
        failures=failures,
        selection_scope="arXiv 最近提交；去重后按规则+模型评分筛选。",
    )
    tell("Writing report and saving run history...")
    try:
        path = write_report(content, settings.output_dir, now)
    except Exception as exc:
        failures.append(f"报告写入失败：{exc}")
        db.save_error_run(
            started_at=started_at,
            finished_at=datetime.now(settings.zone),
            status="failed",
            failures=failures,
        )
        raise
    finished_at = datetime.now(settings.zone)
    db.save_run(
        started_at=started_at,
        finished_at=finished_at,
        status="completed" if not failures else "completed_with_warnings",
        report_path=str(path),
        date=now.date().isoformat(),
        content=content,
        scored_items=scored_items,
        failures=failures,
    )
    state = SeenState.load(settings.data_dir)
    state.mark_many(selected)
    state.save()
    tell(f"Done. Report written: {path}")
    status = "completed" if not failures else "completed_with_warnings"
    return RunResult(report_path=str(path), failures=failures, status=status)
