from __future__ import annotations

import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".idea", ".pytest_cache"}
SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("generic secret assignment", re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*[\"'][^\"']{12,}[\"']")),
]

@dataclass
class Check:
    id: str
    label: str
    status: str
    points: int
    detail: str
    hint: str = ""

@dataclass
class Report:
    path: str
    project_name: str
    score: int
    grade: str
    checks: List[Check] = field(default_factory=list)
    stack: List[str] = field(default_factory=list)
    entrypoints: List[str] = field(default_factory=list)
    suggested_next_steps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["checks"] = [asdict(c) for c in self.checks]
        return data


def _run_git(path: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True, timeout=3)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _files(path: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for name in files:
            yield Path(root) / name


def _has_any(path: Path, names: Iterable[str]) -> Optional[Path]:
    for name in names:
        candidate = path / name
        if candidate.exists():
            return candidate
    return None


def _detect_stack(path: Path) -> List[str]:
    stack = []
    markers = [
        (("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"), "Python"),
        (("package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json", "bun.lockb"), "JavaScript/TypeScript"),
        (("go.mod",), "Go"), (("Cargo.toml",), "Rust"), (("pom.xml", "build.gradle", "build.gradle.kts"), "JVM"),
        (("Gemfile",), "Ruby"), (("composer.json",), "PHP"), (("Dockerfile", "docker-compose.yml", "compose.yml"), "Docker"),
    ]
    for names, label in markers:
        if _has_any(path, names):
            stack.append(label)
    if (path / ".github" / "workflows").exists():
        stack.append("GitHub Actions")
    return stack or ["Unknown"]


def _entrypoints(path: Path) -> List[str]:
    candidates = []
    for name in ("README.md", "pyproject.toml", "package.json", "Makefile", "Dockerfile", "main.py", "app.py", "src", "cmd"):
        if (path / name).exists():
            candidates.append(name)
    return candidates


def _secret_hits(path: Path) -> List[str]:
    hits = []
    for file in _files(path):
        try:
            if file.stat().st_size > 1_000_000 or file.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".lock"}:
                continue
            text = file.read_text(errors="ignore")
        except OSError:
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{file.relative_to(path)} ({label})")
    return hits[:10]


def build_report(path: Union[str, Path]) -> Report:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    project_name = root.name
    checks: List[Check] = []

    readme = _has_any(root, ("README.md", "README.rst", "README.txt"))
    checks.append(Check("docs", "README", "pass" if readme else "fail", 15 if readme else 0,
                        str(readme.name) if readme else "No README found",
                        "Add a README with install, quickstart, examples, and troubleshooting."))

    license_file = _has_any(root, ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"))
    checks.append(Check("license", "License", "pass" if license_file else "warn", 10 if license_file else 0,
                        license_file.name if license_file else "No license file",
                        "Add an OSI-approved license so others know how they can use the project."))

    ci = (root / ".github" / "workflows").exists() or _has_any(root, (".gitlab-ci.yml", ".circleci/config.yml"))
    checks.append(Check("ci", "Continuous integration", "pass" if ci else "warn", 15 if ci else 0,
                        "CI configuration found" if ci else "No CI configuration found",
                        "Add a small test workflow that runs on every pull request."))

    tests = any(p.is_dir() and p.name in {"tests", "test", "spec"} for p in root.iterdir())
    tests = tests or any(p.name.startswith("test_") for p in _files(root))
    checks.append(Check("tests", "Tests", "pass" if tests else "warn", 20 if tests else 0,
                        "Test files found" if tests else "No tests found",
                        "Start with one happy-path test and one failure case."))

    git = bool(_run_git(root, "rev-parse", "--show-toplevel"))
    checks.append(Check("git", "Git repository", "pass" if git else "info", 10 if git else 0,
                        "Git metadata found" if git else "Directory is not a Git repository",
                        "Run git init if this project should be version-controlled."))

    env_example = _has_any(root, (".env.example", ".env.sample", ".env.template"))
    env_used = any(p.name in {".env", ".env.local"} for p in root.iterdir())
    checks.append(Check("env", "Environment documentation", "pass" if env_example else ("warn" if env_used else "info"),
                        10 if env_example else 0,
                        env_example.name if env_example else ("Environment file detected but no example" if env_used else "No env file detected"),
                        "Commit an .env.example, never real credentials."))

    secret_hits = _secret_hits(root)
    checks.append(Check("secrets", "Secret scan", "fail" if secret_hits else "pass", 0 if secret_hits else 20,
                        "; ".join(secret_hits) if secret_hits else "No obvious secrets found",
                        "Rotate any exposed credential, remove it from history, and add it to .gitignore." if secret_hits else ""))

    max_score = 100
    score = round(sum(c.points for c in checks) / max_score * 100)
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
    next_steps = [c.hint for c in checks if c.status in {"fail", "warn"} and c.hint][:3]
    return Report(str(root), project_name, score, grade, checks, _detect_stack(root), _entrypoints(root), next_steps)


def render_terminal(report: Report) -> str:
    icon = {"pass": "✓", "warn": "!", "fail": "✗", "info": "·"}
    lines = [f"repo-ritual  {report.project_name}", f"score  {report.score}/100  grade {report.grade}", "", "checks"]
    for check in report.checks:
        lines.append(f"  {icon[check.status]} {check.label:<28} {check.detail}")
    lines += ["", "stack       " + ", ".join(report.stack), "entrypoints " + (", ".join(report.entrypoints) or "none")]
    if report.suggested_next_steps:
        lines += ["", "next steps"] + [f"  - {step}" for step in report.suggested_next_steps]
    return "\n".join(lines)


def render_markdown(report: Report) -> str:
    rows = ["| Status | Check | Detail |", "|---|---|---|"]
    for c in report.checks:
        detail = c.detail.replace("|", "\\|")
        rows.append(f"| {c.status} | {c.label} | {detail} |")
    return "\n".join([f"# {report.project_name}", f"**Score:** `{report.score}/100` · **Grade:** `{report.grade}`", "", *rows, "", f"**Stack:** {', '.join(report.stack)}"])
