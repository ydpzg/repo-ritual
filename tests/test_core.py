from pathlib import Path
from repo_ritual.core import build_report


def test_report_detects_stack_and_docs(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Demo")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp_path / "tests").mkdir()
    report = build_report(tmp_path)
    assert "Python" in report.stack
    assert report.score >= 50
    assert any(check.id == "docs" and check.status == "pass" for check in report.checks)


def test_report_flags_secret(tmp_path: Path):
    (tmp_path / "config.py").write_text("API_" + "KEY = '1234567890abcdef'\n")
    report = build_report(tmp_path)
    assert any(check.id == "secrets" and check.status == "fail" for check in report.checks)
