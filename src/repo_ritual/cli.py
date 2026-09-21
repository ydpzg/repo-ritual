from __future__ import annotations

import argparse
import json
import sys
from .core import build_report, render_html, render_markdown, render_terminal, strict_failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="repo-ritual", description="Turn a repository into a health score and onboarding brief.")
    parser.add_argument("path", nargs="?", default=".", help="Repository path (default: current directory)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON")
    parser.add_argument("--markdown", action="store_true", help="Print a Markdown report")
    parser.add_argument("--html", action="store_true", help="Print a standalone HTML report")
    parser.add_argument("--strict", action="store_true", help="Return non-zero for warnings as well as failures")
    parser.add_argument("--config", help="Path to repo-ritual.toml (default: repository root)")
    args = parser.parse_args(argv)
    formats = sum(bool(value) for value in (args.as_json, args.markdown, args.html))
    if formats > 1:
        parser.error("choose only one output format")
    try:
        report = build_report(args.path, config_path=args.config, strict=args.strict)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
    elif args.markdown:
        print(render_markdown(report))
    elif args.html:
        print(render_html(report))
    else:
        print(render_terminal(report))
    return 1 if strict_failures(report) and args.strict else (1 if any(c.status == "fail" for c in report.checks) else 0)


if __name__ == "__main__":
    raise SystemExit(main())
