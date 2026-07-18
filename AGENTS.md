# Repository Guidelines

## Project Structure & Module Organization

`treelang/` contains the library. AST models and evaluation behavior live under
`treelang/trees/`, while providers, prompts, selection, and memory integrations
live under `treelang/ai/`. Unit tests mirror the package beneath `tests/`; the
current suite is in `tests/trees/test_tree.py`. Use `cookbook/` for runnable
examples and notebooks. `evaluation/` contains the regression harness, curated
questions, and evaluation tools. Package metadata and dependencies are declared
in `pyproject.toml` and locked in `uv.lock`.

## Build, Test, and Development Commands

- `uv sync --frozen --all-groups`: install the exact locked development environment.
- `make check`: run linting, type checks, tests with coverage, and package builds.
- `uv run pytest`: run the complete test suite.
- `make format`: apply Ruff lint fixes and formatting.
- `uv run python evaluation/eval.py`: run the LLM evaluation harness; this requires configured provider credentials and may make external API calls.

Python 3.12 or newer is required. Run cookbook scripts with uv, for example
`uv run python cookbook/calculator.py`.

## Coding Style & Naming Conventions

Use four-space indentation and Ruff's formatter. Follow standard Python naming:
`snake_case` for functions, variables, and modules; `PascalCase` for classes;
and `UPPER_CASE` for constants. Add type annotations to public interfaces and
async functions where practical. Keep schema changes in `treelang/trees/schemas/`
and provider-specific behavior in `treelang/ai/`; avoid mixing those concerns.

## Testing Guidelines

Tests run with `pytest`; existing cases use `unittest.IsolatedAsyncioTestCase`
and `AsyncMock` for asynchronous behavior.
Name files `test_*.py`, classes `Test*`, and methods `test_*`. Add focused tests
for success paths, validation failures, and async provider interactions. There is
no documented coverage threshold, but every behavior change should include a
regression test. Run the full suite before opening a pull request.

## Commit & Pull Request Guidelines

Create work from `dev` using `feature/<description>`, `fix/<description>`, or
`hotfix/<description>`, and target pull requests to `dev`. Prefer Conventional
Commits such as `feat(parser): add map validation` or
`fix(provider): handle empty tool output`. PRs should explain what changed and
why, link issues (`Fixes #123`), list verification commands, and note compatibility
or security implications. Update documentation and include screenshots only when
the change has a relevant visual effect.

## Security & Configuration

Copy `.env.example` for local configuration and set `OPENAI_API_KEY` outside
version control. Never commit credentials, generated secrets, or sensitive
evaluation data. Report vulnerabilities according to `SECURITY.md`.
