from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ainewsagent.infrastructure.config import DEFAULT_CATEGORIES, DEFAULT_INTERESTS


DEFAULT_CONFIG = {
    "x_list_url": "",
    "x_accounts": ["openai", "arxiv_cs"],
    "arxiv_categories": DEFAULT_CATEGORIES,
    "max_items": 15,
    "timezone": "Asia/Shanghai",
    "output_dir": "reports",
    "data_dir": "data",
    "x_profile_dir": ".ainewsagent/x-profile",
    "x_browser_channel": "",
    "x_max_posts": 40,
    "arxiv_max_results": 80,
    "interests": DEFAULT_INTERESTS,
    "avoid_topics": ["纯营销", "金融炒作"],
    "reading_level": "technical",
}

DEFAULT_ENV = {
    "MIMO_API_KEY": "your-mimo-api-key",
    "MIMO_BASE_URL": "https://your-mimo-compatible-endpoint",
    "MIMO_MODEL": "your-model-name",
}


@dataclass(frozen=True)
class InitResult:
    config_created: bool
    config_updated: bool
    env_created: bool
    env_updated: bool
    directories: list[Path]


def initialize_project(config_path: Path = Path("config.yaml"), env_path: Path = Path(".env")) -> InitResult:
    config_created, config_updated = _ensure_yaml_config(config_path)
    env_created, env_updated = _ensure_env(env_path)
    directories = [Path("reports"), Path("data"), Path(".ainewsagent")]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    return InitResult(
        config_created=config_created,
        config_updated=config_updated,
        env_created=env_created,
        env_updated=env_updated,
        directories=directories,
    )


def _ensure_yaml_config(path: Path) -> tuple[bool, bool]:
    if not path.exists():
        path.write_text(yaml.safe_dump(DEFAULT_CONFIG, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return True, False

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    updated = False
    for key, value in DEFAULT_CONFIG.items():
        if key not in data:
            data[key] = value
            updated = True
    if updated:
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return False, updated


def _ensure_env(path: Path) -> tuple[bool, bool]:
    if not path.exists():
        path.write_text(_render_env(DEFAULT_ENV), encoding="utf-8")
        return True, False

    existing = path.read_text(encoding="utf-8")
    keys = {
        line.split("=", 1)[0].strip()
        for line in existing.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }
    missing = {key: value for key, value in DEFAULT_ENV.items() if key not in keys}
    if not missing:
        return False, False
    suffix = "\n" if existing.endswith("\n") else "\n\n"
    path.write_text(existing + suffix + _render_env(missing), encoding="utf-8")
    return False, True


def _render_env(values: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
