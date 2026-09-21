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

from repo_ritual.core import render_html, strict_failures
from repo_ritual.cli import main


def test_strict_mode_fails_on_warnings_but_normal_mode_does_not(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Demo")
    normal = build_report(tmp_path)
    strict = build_report(tmp_path, strict=True)
    assert strict_failures(normal)
    assert main([str(tmp_path)]) == 0
    assert main([str(tmp_path), "--strict"]) == 1
    assert strict.mode == "strict"


def test_custom_checks_and_ignore_file(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Demo")
    (tmp_path / "repo-ritual.toml").write_text(
        "[checks]\nlicense = false\n\n[[custom_checks]]\nid = 'docs'\nlabel = 'Public docs'\npath = 'docs'\npoints = 5\nrequired = true\n"
    )
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "sample.txt").write_text("TO" + "KEN = '1234567890abcdef'")
    (tmp_path / ".repo-ritual-ignore").write_text("fixtures/**\n")
    report = build_report(tmp_path)
    assert any(c.id == "custom-docs" and c.status == "fail" for c in report.checks)
    assert not any(c.id == "secrets" and c.status == "fail" for c in report.checks)
    assert any(c.id == "license" and c.status == "info" for c in report.checks)


def test_stack_and_html_are_extended_and_escaped(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Demo")
    (tmp_path / "repo-ritual.toml").write_text("[project]\nname = '<Demo>'\n")
    (tmp_path / "package.json").write_text('{"dependencies":{"react":"1","next":"1"}}')
    (tmp_path / "deno.json").write_text("{}")
    report = build_report(tmp_path)
    assert {"JavaScript/TypeScript", "React", "Next.js", "Deno"}.issubset(report.stack)
    rendered = render_html(report)
    assert "<!doctype html>" in rendered
    assert "&lt;Demo&gt;" in rendered
    assert "https://" not in rendered
