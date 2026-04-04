# Copilot Instructions for InstaKindle

## Workflow: Self-Review Loop

After completing any change, perform a self-review before declaring the work done:

1. **Implement** the requested change.
2. **Lint & format** — Run `ruff check src/ tests/` and `ruff format --check src/ tests/`. Fix all findings.
3. **Type-check** — Run `mypy src/`. Fix all findings.
4. **Unit tests** — Run `pytest`. All tests must pass.
5. **End-to-end validation** — Run the actual flow with `python -m instakindle --help` (or a dry-run equivalent) to confirm the CLI and pipeline still wire up correctly. If the change affects runtime behavior, exercise the affected code path beyond unit tests.
6. **Self-review** — Re-read every changed file. Look for typos, logic errors, missing edge cases, leftover debug code, and inconsistencies with the rest of the codebase.
7. **Repeat** steps 2–6 until there are zero lint errors, zero type errors, all tests pass, and the self-review finds nothing to address.

Only mark the task as complete when all of the above pass on the final iteration.

## Testing

- Every bug fix **must** include a regression test that would have caught the bug.
- Every new behavior **must** include unit tests covering the happy path and key error cases.
- Tests live in `tests/` mirroring the `src/instakindle/` structure.
- Run tests with `pytest`. The project is configured with coverage reporting in `pyproject.toml`.

## Validation Beyond Tests

Do not rely solely on unit tests. After making changes:

- Verify the CLI entrypoint loads: `python -m instakindle --help`
- If you changed config, pipeline, or sender logic, import and instantiate the relevant objects to confirm no import errors or wiring issues.
- If integration tests are feasible without live credentials, add them with the `@pytest.mark.integration` marker.

## Code Quality

- **Lint**: `ruff check src/ tests/` — zero errors required.
- **Format**: `ruff format --check src/ tests/` — zero diffs required. Auto-fix with `ruff format src/ tests/` and `ruff check --fix src/ tests/`.
- **Type-check**: `mypy src/` — zero errors required (strict mode is enabled).
- Do not disable lint rules or type checks to make things pass. Fix the underlying code.

## Documentation

- **`README.md`** stays short: project description, features overview, configuration table, and quick-start guide only. Anything detailed goes under `docs/`.
- **`docs/`** contains all detailed documentation (development setup, deployment, architecture, etc.).
- When changing or adding a feature, update the relevant doc in `docs/`. If no suitable doc exists, create one.
- Markdown files must be properly formatted: consistent heading hierarchy, fenced code blocks with language tags, no trailing whitespace, blank lines around headings and code blocks.

## Implementation Standards

- Get it right in one pass. Gather sufficient context, plan the change, then implement fully — do not leave partial work that requires follow-up prompts.
- When multiple files need changes (source, tests, docs), make all of them in the same task.
- Use the existing project conventions visible in the codebase: `from __future__ import annotations`, logging via `logging.getLogger`, type hints on all public APIs.
- Python 3.11+ is the minimum version. Use modern syntax (`X | Y` unions, etc.) where appropriate.

## Project Commands Reference

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Lint
ruff check src/ tests/
ruff check --fix src/ tests/

# Format
ruff format src/ tests/

# Type-check
mypy src/

# Test
pytest

# Run
python -m instakindle --help
```
