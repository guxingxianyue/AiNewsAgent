from __future__ import annotations

from dataclasses import dataclass
from tempfile import TemporaryDirectory

import httpx

from ainewsagent.infrastructure.config import Settings
from ainewsagent.services.llm import LLMClient, LLMConfigError
from ainewsagent.sources.arxiv import ARXIV_API_URL, build_query
from ainewsagent.sources.x_reader import XReadError, check_x_browser


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
        _check_x_browser(settings),
        _check_x_profile(settings),
    ]


def _check_config(settings: Settings) -> DiagnosticCheck:
    if not settings.x_list_url and not settings.x_accounts:
        return DiagnosticCheck("config", False, "未配置 x_list_url 或 x_accounts，X 来源为空。")
    if settings.max_items <= 0:
        return DiagnosticCheck("config", False, "max_items 必须大于 0。")
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


def _check_x_browser(settings: Settings) -> DiagnosticCheck:
    try:
        with TemporaryDirectory(prefix="ainewsagent-browser-check-") as profile_dir:
            check_x_browser(profile_dir, browser_channel=settings.x_browser_channel)
    except XReadError as exc:
        return DiagnosticCheck("x-browser", False, str(exc))
    except Exception as exc:
        return DiagnosticCheck("x-browser", False, f"浏览器检查失败：{exc}")
    return DiagnosticCheck("x-browser", True, "X 浏览器运行环境可用。")


def _check_x_profile(settings: Settings) -> DiagnosticCheck:
    if not settings.x_profile_dir.exists():
        return DiagnosticCheck("x-profile", False, "尚未创建 X 登录 profile，请运行 ainewsagent login-x。")
    return DiagnosticCheck("x-profile", True, f"已找到 {settings.x_profile_dir}")
