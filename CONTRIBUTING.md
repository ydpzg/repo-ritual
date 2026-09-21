# Contributing

Thanks for helping make the first five minutes in a codebase less painful.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest
pytest -q
```

## Design rules for checks

1. Prefer a deterministic signal over a guess.
2. Never make network calls by default.
3. Never modify the target repository.
4. Every warning must include a concrete next step.
5. Keep the standard-library runtime dependency-free.

## Pull requests

Please include a test for every new detector and explain false-positive tradeoffs in the PR description.
