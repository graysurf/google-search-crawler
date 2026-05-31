# AGENTS.md

This file defines the default working conventions for Codex CLI agents operating in this repository.

## Python Development Guidelines

- Keep cognitive complexity ≤ 15 for key functions. If logic becomes highly branched or deeply nested, refactor into smaller functions and/or use early returns.
- Use `snake_case` for payloads/fields. When emitting or parsing external inputs, ensure `camelCase` ↔ `snake_case` conversions are complete to avoid regressions.
- When constructing sets, prefer set comprehensions (`{...}`) over `set(<generator>)` for readability and consistency.
- Batch submission workflows must record the actual number of items committed and exit with a non-zero status when everything is skipped. Do not add unused variables or remove protective checks.

## Project Conventions

- No additional project-specific conventions are currently defined here. Follow repository documentation (e.g., `README.md`, `docs/`, and `CONTRIBUTING.md`) when available.

## Testing and Verification

### Environment Setup (ruff / mypy / pytest)

- Python virtualenvs are managed by `uv`.
- Create or refresh the repo environment with `uv sync --locked`.
- Run Python-backed tools through `uv run --locked <command>`.
- Dev dependencies (`ruff`, `mypy`, and `pytest`) are tracked in `pyproject.toml` and locked in `uv.lock`.

### Commands

- Lint: `uv run --locked ruff check .`
- Format: `uv run --locked ruff format .`
- Type check: `uv run --locked mypy`
- Tests: `uv run --locked pytest -m smoke`
- If no explicit commands are provided and no code was modified, do not explore or run additional tests; report results as `not run`.

## Response Requirements

- If you modify code, you must follow the Environment Setup section and run the following verification steps (do not skip):
  - `uv run --locked ruff check .`
  - `uv run --locked ruff format .`
  - `uv run --locked mypy`
  - `uv run --locked pytest -m smoke`
- Your response must report each step as `pass`, `failed`, or `not run`.
