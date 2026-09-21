from __future__ import annotations

import argparse
import json
import sys
from .core import build_report, render_markdown, render_terminal


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="repo-ritual", description="Turn a repository into a health score and onboarding brief.")
    parser.add_argument("path", nargs="?", default=".", help="Repository path (default: current directory)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON")
    parser.add_argument("--markdown", action="store_true", help="Print a Markdown report")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
    elif args.markdown:
        print(render_markdown(report))
    else:
        print(render_terminal(report))
    return 0 if not any(c.status == "fail" for c in report.checks) else 1

if __name__ == "__main__":
    raise SystemExit(main())
