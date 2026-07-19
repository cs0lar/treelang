# Repository Guidelines

## Project Structure & Module Organization

`treelang/` contains the library. AST models and evaluation behavior live under
`treelang/trees/`, while providers, prompts, selection, and memory integrations
live under `treelang/ai/`. Unit tests mirror the package beneath `tests/`; tree
tests are split across `tests/trees/test_ast.py`, `test_nodes.py`, and
`test_tool.py`. Use `cookbook/` for runnable examples and notebooks.
`evaluation/` contains the regression harness, curated
questions, and evaluation tools. Package metadata and dependencies are declared
in `pyproject.toml` and locked in `uv.lock`.

## Build, Test, and Development Commands

- `uv sync --frozen --all-groups`: install the exact locked development environment.
- `make check`: run linting, type checks, tests with coverage, and package builds.
- `uv run pytest`: run the complete test suite.
- `make format`: apply Ruff lint fixes and formatting.
- `uv run python evaluation/eval.py`: run the deterministic offline benchmark and
  compare it with the committed baseline; this requires no credentials or network
  access.

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
for success paths, validation failures, and async provider interactions. The
current branch-coverage floor is 60%; raise it only with corresponding tests.
Every behavior change should include a regression test. Run the full suite before
opening a pull request.

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

## Modernization Roadmap & Session Handoff

Phases 1 through 4 are merged into `dev` through PR #72. They established the
modern build and CI foundation, hardened the public API and execution semantics,
separated schemas, traversal, compilation, execution, and AI transport concerns,
eliminated shared AST mutation during evaluation, and enabled full-package mypy.

Phase 5 is merged through PR #77. It provides versioned offline and live datasets,
typed benchmark results, redacted structured observability and tracing hooks,
committed regression baselines, CI comparison enforcement, and an owner-only
manual live-evaluation workflow with comparable quality, latency, token, and cost
evidence. Phase 6 begins with tag-validated release automation, isolated artifact
smoke tests, generated notes, provenance, and PyPI Trusted Publishing. Before new
work, update `dev` and run:

```sh
git fetch origin
git switch dev
git pull --ff-only
uv sync --frozen --all-groups
make check
```

### Phase 4: Architecture & Full Typing

Start from updated `dev` and keep refactors behind characterization tests.

1. Separate schema models (`schemas/v1.py`), traversal, execution, and callable
   compilation; preserve serialized schema version `1.0` and public imports.
2. Break `ai/arborist.py` into typed configuration, OpenAI transport, response
   models, and orchestration. Inject clients/configuration instead of reading
   environment variables throughout runtime methods.
3. Replace mutable traversal-based lambda argument injection with per-invocation
   execution context so concurrent calls cannot corrupt shared AST nodes.
4. Define typed tool metadata (model, TypedDict, or protocol) instead of raw
   nested dictionaries. Specify cancellation, timeout, and provider-error behavior.
5. Expand mypy module-by-module until all `treelang/` code is checked. Do not
   suppress categories globally; fix or narrowly justify each incompatibility.

Exit criteria: no shared AST mutation during evaluation, full-package mypy in CI,
public API compatibility tests pass, and coverage is at least 75%.

### Phase 5: Evaluation & Observability

Turn `evaluation/` into a reproducible benchmark rather than an ad hoc script.

1. Version datasets and expected outcomes; separate offline deterministic cases
   from credentialed model evaluations.
2. Record parse success, schema validity, execution success, answer correctness,
   latency, tokens, estimated cost, model/provider, and categorized failures.
3. Add deterministic fixtures/fake transports so core evaluation logic runs in CI.
   Run live model evaluations only through a scheduled/manual workflow with secrets.
4. Emit structured logging and optional tracing. Redact API keys, tool secrets,
   prompts, and sensitive outputs by default.
5. Persist machine-readable benchmark results and compare them with an explicit
   regression tolerance; document how to reproduce each published result.

Exit criteria: offline evaluation passes in normal CI, live runs are repeatable,
and releases include comparable quality/latency/cost evidence.

### Phase 6: Release, Security & Documentation

1. Add semantic-version release automation, generated changelog/release notes,
   PyPI Trusted Publishing, isolated wheel/sdist smoke tests, and provenance.
2. Add CodeQL, dependency auditing, Dependabot/Renovate policy, and secret
   scanning in CI. Triage the high-severity Dependabot alert reported during the
   Phase 3 branch push rather than assuming lockfile updates resolve it.
3. Generate API documentation from the supported root exports. Add architecture
   decisions for schema versioning, execution semantics, and provider contracts.
4. Execute cookbook scripts/notebooks in CI where practical so examples cannot
   drift. Document migration steps for compatibility-relevant releases.
5. Configure branch protection on `dev` and `main`: required CI, review, no force
   pushes, and release-only promotion from `dev` to `main`.

Exit criteria: a tagged release is built and published without long-lived
credentials, installed artifacts pass smoke tests, security gates are green, and
documentation matches the released API.
