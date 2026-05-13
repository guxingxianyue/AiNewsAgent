from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from datetime import datetime

import httpx

from ainewsagent.infrastructure.config import Settings
from ainewsagent.services.llm import LLMClient, LLMConfigError
from ainewsagent.infrastructure.database import AgentDatabase
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
        _check_dir("output_dir", settings.output_dir),
        _check_dir("data_dir", settings.data_dir),
        _check_sqlite(settings),
        _check_model_response_risk(),
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


def _check_dir(name: str, path: Path) -> DiagnosticCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".doctor_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        return DiagnosticCheck(name, False, f"{path} 不可写：{exc}")
    return DiagnosticCheck(name, True, f"{path} 可写。")


def _check_sqlite(settings: Settings) -> DiagnosticCheck:
    try:
        db = AgentDatabase(settings.database_path)
        with sqlite3.connect(db.path) as conn:
            conn.execute(
                "INSERT INTO runs (started_at, finished_at, status, report_path, failures_json) VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now(settings.zone).isoformat(),
                    datetime.now(settings.zone).isoformat(),
                    "doctor_probe",
                    "",
                    "[]",
                ),
            )
            conn.execute("DELETE FROM runs WHERE status = 'doctor_probe'")
    except Exception as exc:
        return DiagnosticCheck("sqlite", False, f"SQLite 初始化或写入失败：{exc}")
    return DiagnosticCheck("sqlite", True, f"SQLite 正常：{settings.database_path}")


def _check_model_response_risk() -> DiagnosticCheck:
    detail = (
        "无法在 doctor 阶段保证模型始终返回合法 JSON；"
        "运行时已内置评分 JSON 解析失败降级与告警，请关注 run 历史中的 warning。"
    )
    return DiagnosticCheck("llm_response_format", True, detail)
