from __future__ import annotations

from dataclasses import dataclass

import httpx

from ainewsagent.infrastructure.config import Settings
from ainewsagent.services.llm import LLMClient, LLMConfigError
from ainewsagent.sources.arxiv import ARXIV_API_URL, build_query


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    ok: bool
    detail: str


def run_diagnostics(settings: Settings) -> list[DiagnosticCheck]:
    return [
        _check_config(settings),
        _check_mimo(),
        _check_arxiv(settings),
    ]


def _check_config(settings: Settings) -> DiagnosticCheck:
    if settings.max_items <= 0:
        return DiagnosticCheck("config", False, "max_items 必须大于 0。")
    if not settings.arxiv_categories:
        return DiagnosticCheck("config", False, "arxiv_categories 不能为空。")
    return DiagnosticCheck("config", True, "配置文件可读取。")


def _check_mimo() -> DiagnosticCheck:
    try:
        client = LLMClient.from_env()
    except LLMConfigError as exc:
        return DiagnosticCheck("mimo", False, str(exc))
    return DiagnosticCheck("mimo", True, f"已配置模型 {client.model}，base_url={client.base_url}")


def _check_arxiv(settings: Settings) -> DiagnosticCheck:
    params = {
        "search_query": build_query(settings.arxiv_categories[:1] or ["cs.AI"]),
        "start": "0",
        "max_results": "1",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    try:
        response = httpx.get(ARXIV_API_URL, params=params, timeout=15.0, headers={"User-Agent": "ainewsagent/0.1"})
        response.raise_for_status()
    except Exception as exc:
        return DiagnosticCheck("arxiv", False, f"arXiv API 暂不可用：{exc}")
    return DiagnosticCheck("arxiv", True, "arXiv API 可访问。")
