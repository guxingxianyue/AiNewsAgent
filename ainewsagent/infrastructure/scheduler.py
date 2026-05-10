from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path


def install_launch_agent(project_dir: Path, hour: int = 8, minute: int = 0) -> Path:
    launch_agents = Path.home() / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agents / "com.ainewsagent.daily-briefing.plist"
    log_dir = project_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    program = sys.executable
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"MIMO_API_KEY", "MIMO_BASE_URL", "MIMO_MODEL", "PATH"}
    }
    payload = {
        "Label": "com.ainewsagent.daily-briefing",
        "ProgramArguments": [program, "-m", "ainewsagent", "run-once"],
        "WorkingDirectory": str(project_dir),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(log_dir / "launchd.out.log"),
        "StandardErrorPath": str(log_dir / "launchd.err.log"),
        "EnvironmentVariables": env,
    }
    plist_path.write_bytes(plistlib.dumps(payload))
    return plist_path
