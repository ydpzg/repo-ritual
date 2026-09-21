from __future__ import annotations

import fnmatch
import html
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

IGNORED_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "dist", "build",
    "__pycache__", ".idea", ".pytest_cache", ".mypy_cache", ".tox", "coverage",
    ".next", ".nuxt", "target", "vendor",
}
IGNORED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".tar", ".gz", ".lock"}
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
    mode: str = "normal"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["checks"] = [asdict(c) for c in self.checks]
        data["strict_failures"] = strict_failures(self)
        return data


def _run_git(path: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(path), *args], text=True, capture_output=True, timeout=3)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _load_ignore_patterns(path: Path) -> List[str]:
    ignore_file = path / ".repo-ritual-ignore"
    try:
        return [line.strip() for line in ignore_file.read_text().splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
    except OSError:
        return []


def _is_ignored(relative: str, patterns: Sequence[str]) -> bool:
    normalized = relative.replace(os.sep, "/")
    return any(fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(Path(normalized).name, pattern)
               for pattern in patterns)


def _files(path: Path, ignore_patterns: Sequence[str] = ()) -> Iterable[Path]:
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        relative_root = root_path.relative_to(path)
        dirs[:] = [d for d in dirs
                   if d not in IGNORED_DIRS and not _is_ignored(str(relative_root / d), ignore_patterns)]
        for name in files:
            candidate = root_path / name
            if not _is_ignored(str(candidate.relative_to(path)), ignore_patterns):
                yield candidate


def _has_any(path: Path, names: Iterable[str]) -> Optional[Path]:
    for name in names:
        candidate = path / name
        if candidate.exists():
            return candidate
    return None


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(errors="ignore"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _detect_stack(path: Path) -> List[str]:
    stack: List[str] = []
    markers: List[Tuple[Sequence[str], str]] = [
        (("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"), "Python"),
        (("go.mod",), "Go"), (("Cargo.toml",), "Rust"),
        (("pom.xml", "build.gradle", "build.gradle.kts"), "JVM"),
        (("Gemfile",), "Ruby"), (("composer.json",), "PHP"),
        (("Dockerfile", "docker-compose.yml", "compose.yml"), "Docker"),
        (("deno.json", "deno.jsonc"), "Deno"), (("mix.exs",), "Elixir"),
        (("Package.swift",), "Swift"), (("Makefile",), "Make"),
        (("CMakeLists.txt",), "CMake"),
        (("kustomization.yaml", "kustomization.yml", "Chart.yaml"), "Kubernetes"),
    ]
    for names, label in markers:
        if _has_any(path, names):
            stack.append(label)
    if list(path.glob("*.csproj")) or list(path.glob("*.sln")):
        stack.append(".NET")
    if list(path.glob("*.tf")):
        stack.append("Terraform")
    package = _read_json(path / "package.json")
    dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    if package:
        stack.append("JavaScript/TypeScript")
        if any(name in dependencies for name in ("react", "react-dom")):
            stack.append("React")
        if "next" in dependencies:
            stack.append("Next.js")
        if "vue" in dependencies:
            stack.append("Vue")
        if "svelte" in dependencies:
            stack.append("Svelte")
        if "astro" in dependencies or list(path.glob("astro.config.*")):
            stack.append("Astro")
    elif _has_any(path, ("pnpm-lock.yaml", "yarn.lock", "package-lock.json", "bun.lockb")):
        stack.append("JavaScript/TypeScript")
    if list(path.glob("svelte.config.*")) and "Svelte" not in stack:
        stack.append("Svelte")
    if (path / ".github" / "workflows").exists():
        stack.append("GitHub Actions")
    return list(dict.fromkeys(stack)) or ["Unknown"]


def _entrypoints(path: Path) -> List[str]:
    candidates = []
    for name in ("README.md", "pyproject.toml", "package.json", "Makefile", "Dockerfile", "main.py", "app.py", "src", "cmd"):
        if (path / name).exists():
            candidates.append(name)
    return candidates


def _placeholder_secret(text: str, file: Path) -> bool:
    if file.name in {".env.example", ".env.sample", ".env.template"}:
        lowered = text.lower()
        return any(marker in lowered for marker in ("change_me", "changeme", "example-token", "your-token", "replace-me"))
    return False


def _secret_hits(path: Path, ignore_patterns: Sequence[str] = ()) -> List[str]:
    hits: List[str] = []
    for file in _files(path, ignore_patterns):
        try:
            if file.name in {".repo-ritual-ignore"} or file.stat().st_size > 1_000_000 or file.suffix.lower() in IGNORED_SUFFIXES:
                continue
            text = file.read_text(errors="ignore")
        except OSError:
            continue
        if _placeholder_secret(text, file):
            continue
        for label, pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{file.relative_to(path)}:{line} ({label})")
                break
    return hits[:10]


def _parse_toml_fallback(text: str) -> Dict[str, Any]:
    """Parse the small, documented subset needed on Python 3.9/3.10."""
    result: Dict[str, Any] = {"checks": {}, "custom_checks": []}
    section: Optional[str] = None
    current: Optional[Dict[str, Any]] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[custom_checks]]":
            current = {}
            result["custom_checks"].append(current)
            section = "custom_checks"
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if value.lower() in {"true", "false"}:
            parsed: Any = value.lower() == "true"
        elif (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            parsed = value[1:-1]
        else:
            try:
                parsed = int(value)
            except ValueError:
                parsed = value
        if section == "custom_checks" and current is not None:
            current[key] = parsed
        elif section == "checks":
            result["checks"][key] = parsed
        else:
            result.setdefault(section or "project", {})[key] = parsed
    return result


def load_config(root: Path, config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    candidate = Path(config_path).expanduser() if config_path else root / "repo-ritual.toml"
    if not candidate.exists():
        if config_path:
            raise ValueError(f"Config file not found: {candidate}")
        return {}
    try:
        import tomllib  # type: ignore[attr-defined]
        with candidate.open("rb") as handle:
            data = tomllib.load(handle)
        return data if isinstance(data, dict) else {}
    except ModuleNotFoundError:
        try:
            return _parse_toml_fallback(candidate.read_text())
        except OSError as exc:
            raise ValueError(f"Could not read config {candidate}: {exc}") from exc
    except (OSError, ValueError) as exc:
        raise ValueError(f"Invalid config {candidate}: {exc}") from exc


def _enabled(config: Dict[str, Any], check_id: str) -> bool:
    checks = config.get("checks", {})
    return checks.get(check_id, True) is not False


def _custom_checks(root: Path, config: Dict[str, Any]) -> List[Check]:
    checks: List[Check] = []
    for index, item in enumerate(config.get("custom_checks", []) or []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        relative = str(item["path"])
        target = root / relative
        label = str(item.get("label") or relative)
        points = max(0, int(item.get("points", 5)))
        required = bool(item.get("required", False))
        exists = target.exists()
        status = "pass" if exists else ("fail" if required else "warn")
        checks.append(Check(f"custom-{item.get('id', index + 1)}", label, status, points if exists else 0,
                            f"Found {relative}" if exists else f"Missing {relative}",
                            str(item.get("hint") or f"Add {relative} to satisfy the custom repository check.")))
    return checks


def build_report(path: Union[str, Path], config_path: Optional[Union[str, Path]] = None, strict: bool = False) -> Report:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    config = load_config(root, config_path)
    project_name = str(config.get("project", {}).get("name") or root.name)
    ignore_patterns = _load_ignore_patterns(root)
    checks: List[Check] = []

    def add(check_id: str, label: str, status: str, points: int, detail: str, hint: str) -> None:
        if not _enabled(config, check_id):
            checks.append(Check(check_id, label, "info", 0, "Disabled by repo-ritual.toml", ""))
        else:
            checks.append(Check(check_id, label, status, points, detail, hint))

    readme = _has_any(root, ("README.md", "README.rst", "README.txt"))
    add("docs", "README", "pass" if readme else "fail", 15 if readme else 0,
        str(readme.name) if readme else "No README found", "Add a README with install, quickstart, examples, and troubleshooting.")
    license_file = _has_any(root, ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"))
    add("license", "License", "pass" if license_file else "warn", 10 if license_file else 0,
        license_file.name if license_file else "No license file", "Add an OSI-approved license so others know how they can use the project.")
    ci = (root / ".github" / "workflows").exists() or _has_any(root, (".gitlab-ci.yml", ".circleci/config.yml"))
    add("ci", "Continuous integration", "pass" if ci else "warn", 15 if ci else 0,
        "CI configuration found" if ci else "No CI configuration found", "Add a small test workflow that runs on every pull request.")
    tests = any(p.is_dir() and p.name in {"tests", "test", "spec"} for p in root.iterdir())
    tests = tests or any(p.name.startswith("test_") for p in _files(root, ignore_patterns))
    add("tests", "Tests", "pass" if tests else "warn", 20 if tests else 0,
        "Test files found" if tests else "No tests found", "Start with one happy-path test and one failure case.")
    git = bool(_run_git(root, "rev-parse", "--show-toplevel"))
    add("git", "Git repository", "pass" if git else "info", 10 if git else 0,
        "Git metadata found" if git else "Directory is not a Git repository", "Run git init if this project should be version-controlled.")
    env_example = _has_any(root, (".env.example", ".env.sample", ".env.template"))
    env_used = any(p.name in {".env", ".env.local"} for p in root.iterdir())
    add("env", "Environment documentation", "pass" if env_example else ("warn" if env_used else "info"), 10 if env_example else 0,
        env_example.name if env_example else ("Environment file detected but no example" if env_used else "No env file detected"), "Commit an .env.example, never real credentials.")
    secret_hits = _secret_hits(root, ignore_patterns)
    add("secrets", "Secret scan", "fail" if secret_hits else "pass", 0 if secret_hits else 20,
        "; ".join(secret_hits) if secret_hits else "No obvious secrets found", "Rotate any exposed credential, remove it from history, and add it to .gitignore." if secret_hits else "")
    custom = _custom_checks(root, config)
    checks.extend(custom)

    base_weights = {"docs": 15, "license": 10, "ci": 15, "tests": 20, "git": 10, "env": 10, "secrets": 20}
    possible = sum(weight for check_id, weight in base_weights.items() if _enabled(config, check_id))
    possible += sum(max(0, int(item.get("points", 5))) for item in (config.get("custom_checks", []) or []) if isinstance(item, dict) and item.get("path"))
    earned = sum(c.points for c in checks)
    score = round(earned / possible * 100) if possible else 0
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
    next_steps = [c.hint for c in checks if c.status in {"fail", "warn"} and c.hint][:5]
    return Report(str(root), project_name, score, grade, checks, _detect_stack(root), _entrypoints(root), next_steps, "strict" if strict else "normal")


def strict_failures(report: Report) -> List[str]:
    return [c.id for c in report.checks if c.status in {"fail", "warn"}]


def render_terminal(report: Report) -> str:
    icon = {"pass": "✓", "warn": "!", "fail": "✗", "info": "·"}
    lines = [f"repo-ritual  {report.project_name}", f"score  {report.score}/100  grade {report.grade}  mode {report.mode}", "", "checks"]
    for check in report.checks:
        lines.append(f"  {icon.get(check.status, '?')} {check.label:<28} {check.detail}")
    lines += ["", "stack       " + ", ".join(report.stack), "entrypoints " + (", ".join(report.entrypoints) or "none")]
    if report.suggested_next_steps:
        lines += ["", "next steps"] + [f"  - {step}" for step in report.suggested_next_steps]
    if report.mode == "strict":
        failures = strict_failures(report)
        lines += ["", "strict failures  " + (", ".join(failures) if failures else "none")]
    return "\n".join(lines)


def render_markdown(report: Report) -> str:
    rows = ["| Status | Check | Detail |", "|---|---|---|"]
    for c in report.checks:
        detail = c.detail.replace("|", "\\|")
        rows.append(f"| {c.status} | {c.label} | {detail} |")
    lines = [f"# {report.project_name}", f"**Score:** `{report.score}/100` · **Grade:** `{report.grade}` · **Mode:** `{report.mode}", "", *rows, "", f"**Stack:** {', '.join(report.stack)}"]
    if report.suggested_next_steps:
        lines += ["", "## Next steps", *[f"- {step}" for step in report.suggested_next_steps]]
    return "\n".join(lines)


def render_html(report: Report) -> str:
    esc = lambda value: html.escape(str(value))
    colors = {"pass": "#14804a", "warn": "#b26a00", "fail": "#c0392b", "info": "#667085"}
    checks = "\n".join(
        f'<tr><td><span class="badge" style="background:{colors.get(c.status, colors["info"])}">{esc(c.status)}</span></td>'
        f'<td><strong>{esc(c.label)}</strong></td><td>{esc(c.detail)}</td></tr>' for c in report.checks
    )
    steps = "".join(f"<li>{esc(step)}</li>" for step in report.suggested_next_steps) or "<li>Nothing urgent detected.</li>"
    stack = " ".join(f'<span class="tag">{esc(item)}</span>' for item in report.stack)
    entries = ", ".join(esc(item) for item in report.entrypoints) or "none"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(report.project_name)} · repo-ritual</title><style>
:root{{color-scheme:light dark;--bg:#f7f8fa;--card:#fff;--text:#182230;--muted:#667085;--line:#e5e7eb}}@media(prefers-color-scheme:dark){{:root{{--bg:#101828;--card:#182230;--text:#f2f4f7;--muted:#98a2b3;--line:#344054}}}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:980px;margin:0 auto;padding:48px 20px}}.hero{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:28px}}h1{{margin:0 0 6px;font-size:32px}}h2{{font-size:18px;margin:0 0 14px}}.muted{{color:var(--muted)}}.score{{font-size:42px;font-weight:800;white-space:nowrap}}.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px;margin:16px 0;box-shadow:0 4px 20px #0000000d}}table{{width:100%;border-collapse:collapse}}th,td{{padding:12px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}th{{color:var(--muted);font-weight:600}}.badge{{color:#fff;border-radius:999px;padding:3px 8px;font-size:12px;font-weight:700;text-transform:uppercase}}.tag{{display:inline-block;background:#eef4ff;color:#2457c5;border-radius:999px;padding:4px 10px;margin:3px 4px 3px 0;font-size:13px}}ul{{margin:0;padding-left:22px}}footer{{color:var(--muted);font-size:13px;margin-top:24px}}
</style></head><body><main><section class="hero"><div><h1>{esc(report.project_name)}</h1><div class="muted">repo-ritual · {esc(report.mode)} mode</div></div><div class="score">{report.score}<span class="muted" style="font-size:18px">/100 · {esc(report.grade)}</span></div></section>
<section class="card"><h2>Checks</h2><table><thead><tr><th>Status</th><th>Check</th><th>Detail</th></tr></thead><tbody>{checks}</tbody></table></section>
<section class="card"><h2>Stack</h2><div>{stack}</div><p class="muted"><strong>Entrypoints:</strong> {entries}</p></section>
<section class="card"><h2>Next steps</h2><ul>{steps}</ul></section><footer>Generated by repo-ritual. This is a heuristic first pass, not a replacement for security tooling.</footer></main></body></html>'''
