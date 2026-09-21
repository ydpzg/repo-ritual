# repo-ritual

> **A 30-second health check and onboarding brief for any codebase.**

[![CI](https://github.com/ydpzg/repo-ritual/actions/workflows/test.yml/badge.svg)](https://github.com/ydpzg/repo-ritual/actions/workflows/test.yml)
[![repo-ritual](https://github.com/ydpzg/repo-ritual/actions/workflows/repo-ritual.yml/badge.svg)](https://github.com/ydpzg/repo-ritual/actions/workflows/repo-ritual.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-zero-2ea44f)](https://github.com/ydpzg/repo-ritual)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

New repo. Old repo. A repo you inherited five minutes ago.

Run one command and get the useful first answers:

- What stack is this?
- Is there a README, a license, CI, and tests?
- Is an environment file documented?
- Did someone accidentally commit an obvious secret?
- What should I fix first?

## Quickstart

```bash
# no install required
PYTHONPATH=src python -m repo_ritual .

# or install the CLI
python -m pip install -e .
repo-ritual /path/to/project
```

## v0.2 highlights

- `--strict` turns warnings into CI failures while normal mode only blocks on obvious secret findings.
- `--markdown`, `--json`, and new `--html` output modes work in scripts and CI.
- The HTML report is a self-contained file: inline CSS, no network calls, and escaped project content.
- `repo-ritual.toml` adds custom required/optional path checks and lets you disable built-in checks.
- `.repo-ritual-ignore` excludes fixtures and known examples from the heuristic secret scan.
- Stack detection now covers Deno, Elixir, Swift, .NET, Terraform, Kubernetes, Make/CMake, React, Next.js, Vue, Svelte, and Astro.
- The included GitHub Action comments or updates a report on every pull request.

## Output formats

```bash
repo-ritual . --markdown > repo-report.md
repo-ritual . --json > repo-report.json
repo-ritual . --html > repo-report.html
open repo-report.html                 # macOS
# xdg-open repo-report.html           # Linux
```

### Exit codes

- `0`: no blocking findings
- `1`: a secret was found, or `--strict` found a warning/failure
- `2`: invalid path, configuration, or command-line arguments

## Custom checks

Copy [`repo-ritual.toml.example`](repo-ritual.toml.example) to `repo-ritual.toml`:

```toml
[project]
name = "my-api"

[checks]
# Disable a built-in check when it is not meaningful for your project.
# license = false

[[custom_checks]]
id = "dockerfile"
label = "Dockerfile"
path = "Dockerfile"
points = 5
required = true
hint = "Add a Dockerfile for a reproducible runtime image."
```

A missing optional custom check is a warning; a missing `required = true` check is a failure. On Python 3.11+, the standard-library TOML parser is used. Python 3.9/3.10 use the small documented subset needed by this file.

For false positives in examples or fixtures, copy [`.repo-ritual-ignore.example`](.repo-ritual-ignore.example) to `.repo-ritual-ignore` and add one glob per line.

## What it checks

| Area | Signal |
|---|---|
| Documentation | README presence |
| Collaboration | LICENSE presence |
| Delivery | CI configuration |
| Confidence | Test files |
| Source control | Git metadata |
| Configuration | `.env.example` / `.env.sample` |
| Safety | A small set of obvious secret patterns |
| Orientation | Stack markers and likely entrypoints |
| Customization | `repo-ritual.toml` path checks |

## GitHub Action

The optional workflow at `.github/workflows/repo-ritual.yml` runs in strict mode on pull requests. It uses a hidden marker to update one existing comment instead of creating a new comment on every push. It intentionally uses `pull_request`, not `pull_request_target`, so untrusted pull-request code is not executed with write privileges. For fork PRs, GitHub may restrict comment permissions according to repository policy.

## Why this exists

Most codebase audits are either heavyweight scanners or a checklist in someone's head. `repo-ritual` sits in the gap: a fast, local, explainable first pass that is safe to run before you understand the project.

It is intentionally:

- **Local-first** — files stay on your machine.
- **Dependency-free** — only Python's standard library at runtime.
- **Non-destructive** — it reads; it does not rewrite your repository.
- **Explainable** — every point has a visible check and a practical hint.
- **CI-friendly** — strict mode makes quality gates explicit.

## Contributing

Small, focused pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup and the design rules for new checks.

## Security

This is a heuristic scanner, not a replacement for secret-scanning infrastructure. If it reports a credential, assume the credential is compromised: rotate it, remove it from history, and investigate where it was used.

## License

MIT © 2026 dukelight
