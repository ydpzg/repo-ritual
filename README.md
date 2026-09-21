# repo-ritual

> **A 30-second health check and onboarding brief for any codebase.**

[![CI](https://github.com/dukelight/repo-ritual/actions/workflows/test.yml/badge.svg)](https://github.com/dukelight/repo-ritual/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-zero-2ea44f)](https://github.com/dukelight/repo-ritual)
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

Example output:

```text
repo-ritual  my-api
score  75/100  grade B

checks
  ✓ README                       README.md
  ✓ License                     LICENSE
  ! Continuous integration      No CI configuration found
  ✓ Tests                       Test files found
  ✓ Git repository              Git metadata found
  ! Environment documentation   Environment file detected but no example
  ✓ Secret scan                 No obvious secrets found

stack       Python, Docker
entrypoints README.md, pyproject.toml, Dockerfile, src

next steps
  - Add a small test workflow that runs on every pull request.
  - Commit an .env.example, never real credentials.
```

## Why this exists

Most codebase audits are either heavyweight scanners or a checklist in someone's head. `repo-ritual` sits in the gap: a fast, local, explainable first pass that is safe to run before you understand the project.

It is intentionally:

- **Local-first** — files stay on your machine.
- **Dependency-free** — only Python's standard library at runtime.
- **Non-destructive** — it reads; it does not rewrite your repository.
- **Explainable** — every point has a visible check and a practical hint.
- **CI-friendly** — exit code is non-zero when obvious secrets are detected.

## What it checks today

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

## Output formats

```bash
repo-ritual . --markdown > repo-report.md
repo-ritual . --json > repo-report.json
```

## Roadmap

- [ ] `--strict` mode for CI quality gates
- [ ] Pluggable checks via `repo-ritual.toml`
- [ ] Dependency freshness hints without network access
- [ ] HTML report with a shareable single-file view
- [ ] GitHub Action that comments a score on pull requests
- [ ] More ecosystem detectors (Deno, Elixir, Swift, .NET)

## Contributing

Small, focused pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for local setup and the design rules for new checks.

## Security

This is a heuristic scanner, not a replacement for secret-scanning infrastructure. If it reports a credential, assume the credential is compromised: rotate it, remove it from history, and investigate where it was used.

## License

MIT © 2026 dukelight
