from ainewsagent.application.diagnostics import run_diagnostics
from ainewsagent.infrastructure.config import Settings


def test_doctor_checks_include_storage_and_sqlite(tmp_path):
    settings = Settings(output_dir=tmp_path / "reports", data_dir=tmp_path / "data")
    checks = run_diagnostics(settings)
    names = {check.name for check in checks}
    assert "output_dir" in names
    assert "data_dir" in names
    assert "sqlite" in names
    assert "llm_response_format" in names
