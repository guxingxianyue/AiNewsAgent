from ainewsagent.infrastructure.initializer import initialize_project


def test_initialize_project_creates_config_env_and_dirs(tmp_path):
    config = tmp_path / "config.yaml"
    env = tmp_path / ".env"

    result = initialize_project(config_path=config, env_path=env)

    assert result.config_created is True
    assert result.env_created is True
    assert "interests:" in config.read_text(encoding="utf-8")
    assert "MIMO_API_KEY" in env.read_text(encoding="utf-8")


def test_initialize_project_updates_missing_fields(tmp_path):
    config = tmp_path / "config.yaml"
    env = tmp_path / ".env"
    config.write_text("max_items: 5\n", encoding="utf-8")
    env.write_text("MIMO_API_KEY=abc\n", encoding="utf-8")

    result = initialize_project(config_path=config, env_path=env)

    assert result.config_updated is True
    assert result.env_updated is True
    assert "reading_level:" in config.read_text(encoding="utf-8")
    assert "MIMO_MODEL" in env.read_text(encoding="utf-8")
