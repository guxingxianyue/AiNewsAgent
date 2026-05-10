from __future__ import annotations

from pathlib import Path
from threading import Lock
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from ainewsagent.application.pipeline import run_once
from ainewsagent.infrastructure.config import Settings
from ainewsagent.infrastructure.database import AgentDatabase
from ainewsagent.services.llm import LLMClient, LLMConfigError

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
run_lock = Lock()
markdown = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="AiNewsAgent")
    app.state.settings = settings
    app.state.db = AgentDatabase(settings.database_path)
    app.state.run_status = {"state": "idle", "message": "尚未在 Web 页面触发采集。"}
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        db: AgentDatabase = request.app.state.db
        briefing = db.latest_briefing()
        return templates.TemplateResponse(
            request,
            "briefing.html",
            {
                "briefing": briefing,
                "briefing_html": markdown.render(briefing.content) if briefing else "",
                "briefings": db.recent_briefings(),
                "items": db.items_for_briefing(briefing.id) if briefing else [],
                "run_status": request.app.state.run_status,
                "trends": db.topic_trends(),
                "settings": request.app.state.settings,
            },
        )

    @app.get("/date/{date}", response_class=HTMLResponse)
    def briefing_by_date(request: Request, date: str) -> HTMLResponse:
        db: AgentDatabase = request.app.state.db
        briefing = db.briefing_by_date(date)
        return templates.TemplateResponse(
            request,
            "briefing.html",
            {
                "briefing": briefing,
                "briefing_html": markdown.render(briefing.content) if briefing else "",
                "briefings": db.recent_briefings(),
                "items": db.items_for_briefing(briefing.id) if briefing else [],
                "run_status": request.app.state.run_status,
                "trends": db.topic_trends(),
                "settings": request.app.state.settings,
            },
        )

    @app.get("/items", response_class=HTMLResponse)
    def items(
        request: Request,
        q: str = "",
        source: str = "",
        topic: str = "",
        importance: str = "",
        audience: str = "",
    ) -> HTMLResponse:
        db: AgentDatabase = request.app.state.db
        filters = {
            "q": q,
            "source": source,
            "topic": topic,
            "importance": importance,
            "audience": audience,
        }
        return templates.TemplateResponse(
            request,
            "items.html",
            {
                "items": db.search_briefing_items(
                    query=q,
                    source=source,
                    topic=topic,
                    importance=importance,
                    audience=audience,
                ),
                "briefings": db.recent_briefings(),
                "trends": db.topic_trends(),
                "settings": request.app.state.settings,
                "filters": filters,
                "filter_options": db.filter_options(),
            },
        )

    @app.get("/runs", response_class=HTMLResponse)
    def runs(request: Request) -> HTMLResponse:
        db: AgentDatabase = request.app.state.db
        return templates.TemplateResponse(
            request,
            "runs.html",
            {"runs": db.recent_runs(), "briefings": db.recent_briefings(), "trends": db.topic_trends(), "settings": request.app.state.settings},
        )

    @app.get("/health")
    def health(request: Request) -> dict[str, str]:
        return {
            "status": "ok",
            "database": str(request.app.state.settings.database_path),
            "run_state": str(request.app.state.run_status["state"]),
        }

    @app.post("/api/run")
    def trigger_run(request: Request, background_tasks: BackgroundTasks) -> RedirectResponse:
        if run_lock.locked():
            request.app.state.run_status = {"state": "running", "message": "已有采集任务正在运行。"}
            return RedirectResponse("/", status_code=303)
        request.app.state.run_status = {"state": "running", "message": "采集任务正在运行，请稍后刷新页面。"}
        background_tasks.add_task(_run_agent, request.app)
        return RedirectResponse("/", status_code=303)

    return app


def _run_agent(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    with run_lock:
        started_at = datetime.now(settings.zone)
        try:
            llm = LLMClient.from_env()
            path, failures = run_once(settings, llm)
        except LLMConfigError as exc:
            message = f"Mimo 配置错误：{exc}"
            AgentDatabase(settings.database_path).save_error_run(
                started_at=started_at,
                finished_at=datetime.now(settings.zone),
                status="failed",
                failures=[message],
            )
            app.state.db = AgentDatabase(settings.database_path)
            app.state.run_status = {"state": "failed", "message": message}
            return
        except Exception as exc:
            message = f"采集失败：{exc}"
            AgentDatabase(settings.database_path).save_error_run(
                started_at=started_at,
                finished_at=datetime.now(settings.zone),
                status="failed",
                failures=[message],
            )
            app.state.db = AgentDatabase(settings.database_path)
            app.state.run_status = {"state": "failed", "message": message}
            return
        app.state.db = AgentDatabase(settings.database_path)
        if failures:
            app.state.run_status = {"state": "succeeded", "message": f"已生成 {path}，但有采集警告。"}
        else:
            app.state.run_status = {"state": "succeeded", "message": f"已生成 {path}。"}
