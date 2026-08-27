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
evidence.

Phase 6 is complete and promoted to `main` through PR #105. Release v0.10.1
proved tag-validated automation, isolated wheel/sdist smoke tests, provenance,
generated notes, and PyPI Trusted Publishing. Security gates, dependency policy,
generated API documentation and architecture decisions, executable cookbook CI,
migration guidance, and enforced `dev`/`main` branch policies are active.

Phase 7 is complete through PR #117. Configurable version 1 execution budgets are
merged through PR #110, and the recursive version 2 language contract and
validation model are merged through PR #111. The explicit-stack interpreter and
separate call-depth enforcement are merged through PR #112. Opt-in schema v2
model generation and deterministic recursive evaluation coverage are merged
through PR #113.
Capability-aware strict structured output with validated compatibility fallback
is merged through PR #114, complete pre-execution tool input validation through
PR #115, and property-based and fuzz coverage for language and runtime invariants
through PR #116. Execution resilience and deterministic replay semantics are
merged through PR #117.

Phase 8 is complete through PR #122. Model capability negotiation is separated
from Arborist orchestration through PR #118, and the contract-tested Anthropic
adapter is merged through PR #119. Cross-provider structured output, usage,
failure, timeout, and cancellation behavior is normalized through PR #120. The
generated, continuously validated provider capability and compatibility matrix
is merged through PR #121.
The same versioned live-evaluation cases run across supported providers through
PR #122.

Phase 9 is complete through PR #128. The versioned documentation site is merged
through PR #124, the CLI through PR #125, downstream testing fixtures and
provider contracts through PR #126, and distributed JSON Schema artifacts
through PR #127. Tested end-to-end cookbooks and extension/provider contribution
workflows are merged through PR #128. Release v1.0.0 metadata, changelog, and
migration guidance were promoted to `main`, and v1.0.0 has been released.

Phases 10 through 15 are complete through PR #139. They provide immutable
transformation contracts, conservative pruning, validated expression grafting,
collision-safe program composition, injectable Arborist transformation
strategies, and effect-aware elimination of duplicate pure computations.
Cookbook integration deadlines are merged through PR #138. Release v1.1.0 has
been published. The documentation-site and distributed-schema URL correction is
merged through PR #143, and v1.1.1 has been published. Compiled AST literal
defaults are merged through PR #152, the `cryptography` 50.0.0 security update
and branch reconciliation through PRs #153 and #154, and query-intent-based tree
descriptions through PR #156. Release v1.2.0 has been published. Strict
structured-output schema generation, safe tool-schema fallback, and persistent
provider-rejection negotiation are fixed through PR #162. Release v1.2.1 has
been published. Schema v2 root API, traversal, compilation, and description
parity is merged through PR #167; compiler-authoritative parameter metadata
through PR #169; and nested schema v1 compilation repair through PR #171.
Release v1.3.0 has been published. Phases 16 through 19 are complete through
PRs #180 through #184, providing compiler-only tool vocabulary, an opt-in OpenAI
Responses transport with reasoning configuration, comparable live-evaluation
dimensions, documentation, and hardened Chat Completions AST generation.
Release v1.4.0 is the next planned promotion from `dev` to `main`.

Before new work, update `dev` and run:

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

### Phase 7: Runtime Reliability & Safety

1. Add configurable execution budgets for AST nodes, nesting depth, tool calls,
   concurrency, and wall-clock duration. Complete through PR #110.
2. Define an opt-in version 2 schema for user function declarations, variable
   references, user calls, lexical scope, and recursion while preserving version
   1 compatibility. Complete through PR #111.
3. Implement version 2 evaluation with an explicit stack and a separate
   user-call-depth budget; support direct recursion before mutual recursion and
   model generation. Complete through PR #113.
4. Use provider-supported strict structured output with validated repair as a
   capability-aware fallback. Complete through PR #114.
5. Validate complete tool input schemas, including required fields, types, and
   constraints, before execution. Complete through PR #115.
6. Add property-based and fuzz tests for parsing, traversal, conditionals,
   lambdas, maps, filters, reductions, recursion, and concurrent execution.
   Complete through PR #116.
7. Define retry, idempotency, cancellation, and partial-failure semantics for
   sequential and parallel programs. Add deterministic model/tool replay.
   Complete through PR #117.

Exit criteria: malformed or adversarial ASTs fail safely, configured budgets
cannot be exceeded, and generative tests preserve execution invariants.

### Phase 8: Provider Portability

1. Separate model capability negotiation from Arborist orchestration. Complete
   through PR #118.
2. Add contract-tested adapters for at least one additional model provider.
   Complete through PR #119.
3. Normalize structured-output support, token accounting, rate limits, timeout,
   cancellation, and provider-error translation. Complete through PR #120.
4. Publish and continuously test a provider capability and compatibility matrix.
   Complete through PR #121.
5. Run the same versioned live-evaluation cases across supported providers.
   Complete through PR #122.

Exit criteria: the supported evaluation suite passes against at least two model
providers without application-level changes.

### Phase 9: Developer Experience & Ecosystem

1. Publish a versioned documentation site with generated API references, guides,
   architecture decisions, and migration notes.
   Complete through PR #124.
2. Add a CLI for generating, validating, inspecting, replaying, and executing
   AST programs.
   Complete through PR #125.
3. Publish reusable downstream testing fixtures, fake transports, and provider
   contract suites.
   Complete through PR #126.
4. Distribute the supported JSON Schema and add editor-validation examples.
   Complete through PR #127.
5. Expand cookbooks into tested end-to-end tutorials and document extension and
   provider contribution workflows.
   Complete through PR #128.

Exit criteria: a new user can install Treelang, execute and inspect a validated
program, build a provider, and reproduce benchmarks using documented workflows.

### Phase 10: Tree Transformation Foundation

Define immutable, schema-neutral tree paths, typed change and lineage records,
and transformation results. Keep this phase free of rewriting behavior so the
public contracts can be reviewed independently. Document and test path identity,
root/child handling, deterministic reporting, and compatibility with both schema
versions. Complete through PR #132.

Exit criteria: later transformations can identify nodes and report reproducible
changes without depending on an AI provider or mutating an input tree.

### Phase 11: Conservative Pruning

Implement a deterministic schema v2 pruner with only locally provable rewrites:
remove unreachable user-function definitions and simplify conditionals with
literal boolean conditions. Validate every output and report each change. Keep
schema v1 pruning as a no-op unless a rewrite is equally unambiguous. Complete
through PR #134.

Exit criteria: pruning is idempotent, does not mutate its input, preserves tested
execution results, and never evaluates, combines, or directly rewrites external
tool calls.

### Phase 12: Expression Grafting

Add immutable path-based replacement, wrapping, and grafting for schema v2
expressions. Reject missing paths, incompatible node locations, unbound variables,
invalid call arity, and results exceeding configured structural limits. Complete
through PR #135.

Exit criteria: callers can construct a larger valid program from a base program
and an expression with deterministic transformation records.

### Phase 13: Program Composition & Identifier Hygiene

Combine schema v2 programs in single or parallel mode. Merge their function
definitions, alpha-rename collisions, update calls and lexical references, and
preserve deterministic definition ordering. Complete through PR #136.

Exit criteria: independently valid programs compose without name capture, source
mutation, or application-level changes to their external tool providers.

### Phase 14: Arborist Transformation Strategies

Introduce injectable pruner and grower protocols and make `BaseArborist.prune()`
and `grow()` compatibility-preserving delegates. Keep deterministic local
transformations synchronous; provide a separate asynchronous boundary for
model-guided or evaluation-guided growth.
Complete through PR #137.

Exit criteria: model-specific Arborists do not implement tree rewriting directly,
existing `prune()` callers remain compatible, and the legacy no-argument `grow()`
behavior has a documented migration path.

### Phase 15: Effects, Bindings & Duplicate Computation

Define provider-neutral tool effect metadata for purity, determinism, and
idempotency. Add an opt-in schema construct for local binding or explicit
memoization, then implement common-subexpression elimination only when evaluation
is provably safe under the declared effects and execution policy.
Complete through PR #139.

Exit criteria: duplicate pure computations can execute once and be reused, while
effectful or undeclared tools are never deduplicated by default.

### Phase 16: Compiler Vocabulary Foundation

Define typed configuration and metadata boundaries that separate selected tool
vocabulary and reasoning configuration from provider SDK function-call tools.
Add deterministic tool-catalog rendering that preserves complete JSON Schema
metadata. Keep schema versions 1 and 2 supported; do not make a transport change
implicitly promote callers to schema v2.

Complete through PR #180.

Exit criteria: selected tools can be represented losslessly as compiler context,
existing selectors are unchanged, and current Chat Completions and Anthropic
behavior remains characterized.

### Phase 17: OpenAI Responses Transport

Add an explicit OpenAI Responses API adapter alongside the existing Chat
Completions adapter. Encode system instructions, conversation input, reasoning
effort, and strict JSON Schema output through the Responses API; normalize text
extraction, usage accounting, malformed or empty output, cancellation, timeouts,
provider errors, and structured-output rejection behavior through the existing
transport contracts.

Complete through PR #181.

Exit criteria: callers can explicitly select Responses generation, reasoning
models receive no OpenAI function tools, strict AST output works for either schema
version, and contract tests cover success and failure paths without live access.

### Phase 18: Arborist Configuration & Evaluation Integration

Expose backward-compatible configuration for OpenAI API selection and reasoning
effort, wire provider-neutral request construction into `OpenAIArborist`, and add
live-evaluation dimensions that compare Chat Completions with Responses reasoning.
Keep Chat Completions as the default during this phase and reject incompatible
configuration early rather than silently dropping it.

Complete through PR #182.

Exit criteria: existing applications retain their request path by default, live
evaluation records the selected API and reasoning effort, and Responses requests
continue through the same validation, pruning, execution, and tool-input checks.

### Phase 19: Responses Documentation & Compatibility Evidence

Document the compiler-vocabulary model, explicit Responses configuration, schema
v1/v2 behavior, reasoning-model example, migration considerations, and provider
capability matrix. Add an executable or contract-tested cookbook example and
capture benchmark commands without claiming a quality improvement before live
evidence exists.

Complete through PRs #183 and #184.

Exit criteria: users can reproduce both OpenAI paths, understand why tools are
context rather than function calls in Responses mode, and evaluate semantic AST
quality, latency, token use, and cost with the versioned live harness.
