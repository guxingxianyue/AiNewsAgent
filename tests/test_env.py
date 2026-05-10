import os

from ainewsagent.infrastructure.env import load_dotenv


def test_load_dotenv_sets_missing_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('MIMO_MODEL="mimo-test"\nMIMO_BASE_URL=https://example.com\n', encoding="utf-8")
    monkeypatch.delenv("MIMO_MODEL", raising=False)
    monkeypatch.delenv("MIMO_BASE_URL", raising=False)

    loaded = load_dotenv(env_file)

    assert loaded == {"MIMO_MODEL": "mimo-test", "MIMO_BASE_URL": "https://example.com"}
    assert os.environ["MIMO_MODEL"] == "mimo-test"


def test_load_dotenv_does_not_override_existing_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MIMO_MODEL=from-file\n", encoding="utf-8")
    monkeypatch.setenv("MIMO_MODEL", "from-env")

    loaded = load_dotenv(env_file)

    assert loaded == {}
    assert os.environ["MIMO_MODEL"] == "from-env"
