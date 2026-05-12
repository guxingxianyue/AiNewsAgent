from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ainewsagent.infrastructure.config import Settings
from ainewsagent.infrastructure.database import AgentDatabase
from ainewsagent.infrastructure.state import SeenState
from ainewsagent.services.llm import LLMClient
from ainewsagent.services.ranker import dedupe_items, rank_items
from ainewsagent.services.report import write_report
from ainewsagent.sources.arxiv import fetch_recent_papers
from ainewsagent.domain.models import Item


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
) -> tuple[str, list[str]]:
    def tell(message: str) -> None:
        if progress:
            progress(message)

    started_at = datetime.now(settings.zone)
    now = now or started_at
    candidate_limit = max(settings.max_items * 3, settings.max_items)
    tell("Collecting recent arXiv papers...")
    candidates, failures = collect_candidates(settings, max_items=candidate_limit)
    tell(f"Collected {len(candidates)} candidate papers. Scoring with Mimo...")
    scored_items = llm.score_items(
        candidates,
        settings.max_items,
        interests=settings.interests,
        avoid_topics=settings.avoid_topics,
        reading_level=settings.reading_level,
    )
    selected = [scored.item for scored in scored_items]
    tell(f"Selected {len(scored_items)} papers. Generating briefing...")
    content = llm.create_briefing_from_scored(scored_items, failures)
    tell("Writing report and saving run history...")
    path = write_report(content, settings.output_dir, now)
    finished_at = datetime.now(settings.zone)
    AgentDatabase(settings.database_path).save_run(
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
    return str(path), failures
