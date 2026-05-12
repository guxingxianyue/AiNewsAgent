from __future__ import annotations

from pathlib import Path

import typer

from ainewsagent.application.diagnostics import run_diagnostics
from ainewsagent.application.pipeline import run_once as run_pipeline
from ainewsagent.application.pipeline import collect_candidates
from ainewsagent.infrastructure.config import load_settings
from ainewsagent.infrastructure.env import load_dotenv
from ainewsagent.infrastructure.initializer import initialize_project
from ainewsagent.infrastructure.scheduler import install_launch_agent
from ainewsagent.services.llm import LLMClient, LLMConfigError
from ainewsagent.services.ranker import score_item

app = typer.Typer(help="AiNewsAgent daily AI frontier briefing agent.")


@app.callback()
def main(env_file: Path = typer.Option(Path(".env"), "--env-file", help="Load environment variables from this file.")) -> None:
    load_dotenv(env_file)


@app.command("init")
def init_command(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    env_file: Path = typer.Option(Path(".env"), "--env-output"),
) -> None:
    result = initialize_project(config_path=config, env_path=env_file)
    typer.echo("AiNewsAgent 初始化完成。")
    typer.echo(f"- config: {'created' if result.config_created else 'updated' if result.config_updated else 'unchanged'} ({config})")
    typer.echo(f"- env: {'created' if result.env_created else 'updated' if result.env_updated else 'unchanged'} ({env_file})")
    for directory in result.directories:
        typer.echo(f"- directory ready: {directory}")
    typer.echo("下一步：编辑 .env 填入 Mimo API，再运行 `ainewsagent doctor`。")


@app.command("run-once")
def run_once_command(config: Path = typer.Option(Path("config.yaml"), "--config", "-c")) -> None:
    settings = load_settings(config)
    try:
        llm = LLMClient.from_env()
    except LLMConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc
    path, failures = run_pipeline(settings, llm)
    typer.echo(f"Report written: {path}")
    for failure in failures:
        typer.echo(f"Warning: {failure}")


@app.command("preview")
def preview_command(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    include_seen: bool = typer.Option(False, "--include-seen", help="Include items already recorded in data/seen.json."),
) -> None:
    settings = load_settings(config)
    items, failures = collect_candidates(settings, include_seen=include_seen)
    if failures:
        typer.echo("采集警告：")
        for failure in failures:
            typer.echo(f"- {failure}")
        typer.echo("")

    if not items:
        typer.echo("没有可预览的候选内容。")
        return

    typer.echo(f"候选精选：{len(items)} 条")
    for index, item in enumerate(items, start=1):
        authors = ", ".join(item.authors[:3]) or "未知"
        categories = ", ".join(item.categories[:4]) or "-"
        typer.echo(
            f"\n{index}. [{item.source.value}] score={score_item(item):.1f}\n"
            f"   标题：{item.title}\n"
            f"   作者/账号：{authors}\n"
            f"   分类：{categories}\n"
            f"   时间：{item.published_at.isoformat()}\n"
            f"   链接：{item.url}"
        )


@app.command("doctor")
def doctor_command(config: Path = typer.Option(Path("config.yaml"), "--config", "-c")) -> None:
    settings = load_settings(config)
    checks = run_diagnostics(settings)
    for check in checks:
        status = "OK" if check.ok else "FAIL"
        typer.echo(f"[{status}] {check.name}: {check.detail}")
    if any(not check.ok for check in checks):
        raise typer.Exit(code=1)


@app.command("web")
def web_command(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port", min=1, max=65535),
) -> None:
    import uvicorn

    from ainewsagent.interfaces.web import create_app

    settings = load_settings(config)
    typer.echo(f"AiNewsAgent Web: http://{host}:{port}")
    uvicorn.run(create_app(settings), host=host, port=port)


@app.command("install-schedule")
def install_schedule_command(
    project_dir: Path = typer.Option(Path.cwd(), "--project-dir"),
    hour: int = typer.Option(8, "--hour", min=0, max=23),
    minute: int = typer.Option(0, "--minute", min=0, max=59),
) -> None:
    path = install_launch_agent(project_dir.resolve(), hour=hour, minute=minute)
    typer.echo(f"LaunchAgent installed: {path}")
    typer.echo("Load it with: launchctl load ~/Library/LaunchAgents/com.ainewsagent.daily-briefing.plist")
