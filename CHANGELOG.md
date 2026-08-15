# Changelog

## [1.3.0] - 2026-08-15

### Added

- Added schema version 2 support to the root `AST` parsing, representation,
  evaluation, synchronous and asynchronous traversal, and callable compilation
  APIs.
- Added schema version 2 tree descriptions that preserve immutable source
  programs while retaining the described copy on the response.
- Added typed compiler-authoritative parameter source metadata for schema
  versions 1 and 2 through `CompiledParameterSource`,
  `compiled_parameter_sources()`, and `__treelang_parameters__`.
- Added named, overridable schema version 2 literal defaults for external-tool
  arguments and direct user-function call arguments, with isolated mutable
  defaults and deterministic duplicate-name suffixes.

### Fixed

- Fixed schema version 1 compilation after multiple sibling nested calls by
  unwinding all completed tool frames before resolving a following value.
- Replaced leaked `KeyError` failures for values that name no enclosing tool
  parameter with contextual `ASTCompilationError` failures.

### Compatibility

- Schema version 1 parsing, execution, traversal, callable signatures, and
  descriptions retain their existing behavior.
- Schema version 2 remains opt-in through an explicit `schema_version: "2.0"`.
- Existing compiled callables remain valid; parameter-source metadata and v2
  support are additive.
- Schema versions 1.0 and 2.0 remain unchanged.

## [1.2.1] - 2026-08-08

### Fixed

- Corrected strict JSON Schema generation so references no longer carry
  provider-rejected sibling keywords, allowing supported OpenAI models to use
  strict structured output without an unnecessary compatibility retry.
- Select compatibility output before a request when a tool accepts object
  parameters that the strict AST projection cannot express, including nullable
  object type unions.
- Remember provider rejection of strict output per model and schema version so
  subsequent requests do not repeat a known-to-fail round trip.

### Compatibility

- Existing structured-output configuration and negotiator method signatures
  remain unchanged.
- Schema versions 1.0 and 2.0 remain unchanged.

## [1.2.0] - 2026-08-07

### Added

- Added overridable keyword-only defaults to compiled tools for non-null AST
  literals. Required placeholders remain required, while mutable defaults are
  snapshotted and deep-copied for every invocation.

### Changed

- Tree descriptions now use the original user query as the source of workflow
  intent and the AST as implementation evidence, producing reusable
  `snake_case` names instead of names derived from low-level tool calls or
  instance-specific values.

### Compatibility

- Existing compiled-tool arguments remain valid; callers may now omit arguments
  backed by non-null AST literals or explicitly override their defaults.
- `EvalResponse.describe()` retains its existing signature and return type.
- Schema versions 1.0 and 2.0 remain unchanged.

### Security

- Updated the locked transitive `cryptography` dependency to 50.0.0 to address
  `PYSEC-2026-3552` and `CVE-2026-69247`.

## [1.1.1] - 2026-08-03

### Fixed

- Corrected the GitHub Pages owner in the README, package metadata, MkDocs
  configuration, editor examples, and canonical JSON Schema identifiers so
  documentation and schema links resolve at `https://cs0lar.github.io/treelang/`.

## [1.1.0] - 2026-08-03

### Added

- Added immutable, schema-neutral tree paths, typed transformation changes,
  lineage records, and validated transformation results.
- Added conservative schema version 2 pruning for unreachable function
  definitions and literal conditionals.
- Added immutable expression replacement, wrapping, and grafting with structural
  and lexical validation.
- Added deterministic schema version 2 program composition with collision-safe
  identifier renaming and preserved lexical references.
- Added injectable pruning and growth strategies for Arborists, including a
  separate asynchronous boundary for guided transformations.
- Added provider-neutral tool-effect metadata and opt-in local bindings for safe
  common-subexpression elimination of pure, deterministic computations.

### Changed

- Bounded notebook execution, MCP startup, individual MCP operations, and MCP
  cleanup in cookbook integration checks so stalled examples fail predictably.
- Updated development dependencies within their supported compatibility ranges.

### Compatibility

- Existing schema version 1 and version 2 programs remain compatible; bindings
  and transformation APIs are opt-in.
- Existing Arborist `prune()` callers remain compatible, and legacy no-argument
  `grow()` behavior retains its documented migration path.
- Tools without explicit safe effect declarations are never deduplicated.
- Python 3.12 or newer remains required.

## [1.0.0] - 2026-07-27

Treelang 1.0 establishes the version 1 language, supported root API, execution
semantics, provider contracts, and serialized artifacts as stable compatibility
surfaces. Schema version 2 recursion remains explicit and opt-in.

### Added

- Added configurable node, nesting, call-depth, tool-call, concurrency, and
  wall-clock execution budgets.
- Added opt-in schema version 2 with lexical scope, user functions, explicit
  calls, direct recursion, and an explicit-stack interpreter.
- Added deterministic retry, idempotency, cancellation, parallel
  partial-failure, model replay, and tool replay semantics.
- Added complete pre-execution JSON Schema validation for evaluated tool inputs,
  plus property-based and fuzz coverage for language/runtime invariants.
- Added the optional Anthropic transport and a generated, continuously validated
  OpenAI/Anthropic capability matrix.
- Added provider-selectable live evaluation using the same versioned dataset,
  metrics, workflow controls, and artifact format.
- Added the `treelang` CLI for schema export, generation, validation, inspection,
  execution, and deterministic replay.
- Added framework-neutral downstream model/tool fakes and reusable provider
  contract suites under `treelang.testing`.
- Added canonical Draft 2020-12 artifacts for schema versions 1.0 and 2.0 in the
  wheel and documentation site, with editor mappings and CI drift enforcement.
- Added a versioned documentation site and credential-free, executable
  quickstart and custom-provider tutorials.

### Changed

- Separated model capability negotiation from Arborist orchestration and
  normalized structured output, usage accounting, timeouts, cancellation,
  rate limits, and provider-error translation.
- Prefer provider-native strict structured output when supported, with validated
  capability-aware compatibility fallback.
- Expanded public documentation around Treelang's plan-first/local-execution
  niche, realistic use cases, limitations, extensions, and provider
  contributions.
- Release documentation is now published by package version with an updated
  `latest` alias after successful tagged releases.

### Compatibility

- Schema version 1.0 serialization and execution remain compatible with the
  0.10 series.
- Schema version 2.0 and recursive model generation require explicit opt-in.
- Python 3.12 or newer remains required.
- Anthropic support remains an optional installation extra; the default
  installation continues to include OpenAI.

### Security

- Generated or untrusted programs can now be constrained by independent
  execution budgets before they reach application tools.
- Complete tool schemas are enforced before invocation, so rejected arguments do
  not consume tool-call budgets or reach providers.
- Provider errors and cancellation are normalized without treating unrelated
  failures as structured-output fallback signals.
- Live model evaluation remains manual, owner-only, environment-protected, and
  isolated from pull requests and normal CI.

## [0.10.2] - 2026-07-23

### Added

- Added CodeQL, locked dependency auditing, Dependabot policy, generated API
  documentation, architecture decisions, and executable cookbook checks.
- Added enforced pull-request, review, CI, security, and `dev`-only promotion
  policies for protected branches.
- Added live evaluation dataset 2.0 with an explicit country-to-currency lookup
  contract.

### Changed

- Added compatibility with OpenAI Python SDK 2 while retaining SDK 1 support.
- Updated GitHub Actions to their current Node.js 24 releases and updated
  JupyterLab to 4.6.2.

### Fixed

- Fixed GitHub release creation by providing an explicit repository context when
  downloaded artifacts are processed outside a Git checkout.
- Fixed the live USD-to-JPY evaluation repeatedly passing a country or currency
  name to a tool that requires a three-letter currency code.

### Security

- Updated JupyterLab to address two high-, two moderate-, and one low-severity
  advisory.
- Added mandatory CodeQL and dependency-audit checks to the protected release
  path.

## [0.10.1] - 2026-07-21

### Added

- Added bounded, configurable retries with validation feedback when a model returns invalid JSON or an invalid AST.
- Added semantic validation for lambda bindings and higher-order function arity.
- Added the Australian population reduction to the deterministic offline evaluation dataset and baseline.

### Changed

- Improved Arborist guidance and examples for conditional nodes, lambda placeholders, and reduce initialization.
- Updated cookbook notebooks to run directly in Jupyter and reliably locate their local MCP servers.
- Updated `pydantic-settings` to patched version 2.14.2.

### Fixed

- Fixed malformed conditional and lambda programs reaching execution instead of being corrected or rejected.
- Fixed reduce nodes passing a null accumulator to the first tool invocation; null accumulators now start with the first iterable item.
- Fixed the calculator cookbook generating a conditional program twice and passing wrapped MCP scalar outputs to arithmetic tools.

## [0.10.0] - 2026-07-19

### Added

- Added a supported package-level API and domain-specific exception hierarchy.
- Added deterministic offline and credentialed live evaluation workflows.
- Added structured, redacted observability and optional tracing hooks.
- Added benchmark baselines and regression enforcement.
- Added a tag-validated release pipeline with artifact smoke tests, generated release notes, provenance, and PyPI Trusted
Publishing.

### Changed

- Migrated packaging and development workflows from Poetry to uv and Hatchling.
- Separated AST schemas, traversal, execution, and callable compilation.
- Split Arborist configuration, transport, response, and orchestration concerns.
- Made AST evaluation safe for concurrent invocation without shared mutation.
- Added fully typed provider metadata and full-package mypy enforcement.
- Raised the MCP dependency floor to patched version 1.28.1.

### Removed

- Removed the undocumented `LlamIndexToolProvider`.
- Removed Poetry packaging and its legacy lockfile.

## [0.9.1] - 2026-02-03

### Changed

- In `evaluation/data/tools.py` the `get_largest_city_by_ranking` tool has been renamed to `get_largest_city_by_rank` and the `ranking` parameter has been renamed to `rank` for consistency. This seems to help the agent better understand the parameter.

## [0.9.0] - 2026-01-29

### Added

- Added `mode` and `schema_version` parameters to `TreeProgram`
- Added `ast_json_schema` and `ast_examples` functions to retrieve the JSON schema and example ASTs for a given `schema_version`.

### Changed

- Updated `ARBORIST_SYSTEM_PROMPT` to now include automatically generated AST schema and valid AST examples based on the selected `schema_version`. Correctness rules have also been updated to reflect the selected schema version.
- AST nodes are now pydantic models with strict type checking defining a canonical schema for `treelang` programs.
- Updated all cookbooks and tests to use the new AST schema.
- Updated `Evaluator` to now perform result matching and correctness of AST based on presence of required nodes and structure rather than exact AST matching.
- `AST.repr()` now outputs a full AST in JSON format.

### Fixed

- Parameter binding in higher order functions now using named parameters.

## [0.8.1] - 2025-10-30

### Changed

- Converted `Memory` methods to be asynchronous.

## [0.8.0] - 2025-10-29

### Added

- Added the `Memory` abstract class.
- Added memory support to the `Arborist` class via the `memory` parameter.
- Added a new cookbook `cookbook/memory.ipynb` demonstrating how to use memory with `treelang`.

## [0.7.6] - 2025-09-26

### Changed

- The `EvalResponse` object now specified a value for the `jsontree` property for both `WALK` and `TREE` modes.

- The `calculator.ipynb` cookbook now uses `async.gather` to run the initial set of expressions asynchronously.

## [0.7.5] - 2025-09-21

### Added

- Added the `explain_stream` method to `EvalResponse` to support streamed response explanations.

### Fixed

- the `explain`, ``explain_stream` and `describe` methods now retrieve the LLM model to use from the environment.

## [0.7.4] - 2025-09-21

### Changed

- The `OpenAIArborist` now uses the asynchronous version of the OpenAI API.
- Removed direct dependency on `starlette` and `uvicorn` from `pyproject.toml`.

## [0.7.3] - 2025-09-13

### Added

- Added `query` parameter to `BaseToolSelector.select()`.
- `OpenAIArborist` now passes the query to its `selector`.

## [0.7.2] - 2025-08-08

### Fixed

- Fixed the way in which the `OpenAIArborist` checks whether a model supports the `temperature` parameter.

## [0.7.1] - 2025-07-13

### Changed

- Removed `vcrpy` dependency.

### Fixed

- Instead of throwing an uncaught exception when the output of an MCP tool is not json loadable, we return the content as is in `MCPToolProvider`'s `call_tool()` method.

## [0.7.0] - 2025-07-05

### Added

- Added `TreeFilter` and `TreeReduce`.

### Changed

- Updated `README.md`.
- Added tests for `TreeFilter` and `TreeReduce`.
- Updated the `ARBORIST_SYSTEM_PROMPT` prompt.
- Updated the `Evaluator` with questions for the `filter` and `reduce` operations.

### Fixed

- Fixed the python docs for `TreeMap`.
- Fixed `add()` definition in `calculator.py`.

## [0.6.0] - 2025-06-29

### Added

- Support for functional patters using `TreeLambda` and `TreeMap` nodes.

### Changed

- Added tests for higher order function nodes.
- Updated the `ARBORIST_SYSTEM_PROMPT` prompt.
- Added example of high order function to the `Evaluator`.
- Updated `CONTRIBUTING.md` to include an _Evaluation_ section.
- Added example of loop in `calculator.ipynb` cookbook.

## [0.5.0] - 2025-05-13

### Added

- `TreeConditional` node for support of `if-then-else` conditionals in `treelang`.

### Changed

- Added conditionals support in `AST` parsing, evaluating, visiting and representing (`repr()`)
- Added conditional node tests.
- Added conditional example to `Evaluator`.
- Added example of query with conditional in `calculator.ipynb` cookbook.
- Added `greater_than` tool in `calculator.py`.

### Fixed

- Parameter binding for tool creation when multiple arguments have the same name in `AST.tool()`.

## [0.4.1] - 2025-05-08

### Fixed

- Invalid reference to `self` in `MCPToolProvider`'s `call_too()` method.

## [0.4.0] - 2025-05-07

### Added

- `ToolProvider` abstract class allowing methods other than `MCP` to provide tools for an `Arborist`.
- `MCPToolProvider` - the `MCP` implementation of a `ToolProvider`.
- `LLamaIndexToolProvider` an example provider that uses `llama-index` to manage tools.

### Changed

- `Arborist` and `TreeNode`s now expect a `ToolProvider` instead of an `MCP` session.
- All cookbooks, tests and `Evaluator` updated to use the `MCPToolProvider`.
- `README.md` mentions the `ToolProvider` abstraction.
- Removed the _release branch_ section from `CONTRIBUTING.md`.

## [0.3.1] - 2025-04-26

### Added

- badges to `README.md`

### Changed

- `README.md` wording and layout.

## [0.3.0] - 2025-04-20

### Added

- `describe()` function for `EvalResult`s. It uses an LLM to generate a name and a description for the program represented by the tree passed as argument.
- `AST.tool()` static function. It converts a tree into a tool/callable that can added dynamically to an MCP server.
- asynchronous `AST.avisit()` to allow asynchronous tree visitors.
- `TestToolMethod` unit tests for `AST.tool()`
- `gamestats` cookbook to demonstrate the new functions.

### Changed

- modified `ARBORIST_SYSTEM_PROMPT` to include rules for maintaing the ordering of a tool's arguments.

## [0.2.1] - 2025-04-19

### Fixed

- `ToolFunction` now correctly handles array results from the underlying MCP tool.

## [0.2.0] - 2025-04-06

### Added

- Ability to translate possibly structured data returned by an AST evaluation into plain english for those applications that require the full conversational user experience.
- Evaluation module to evaluate `treelang`'s performance against various scenarios. The initial evaluation tests the ability of `treelang` to generate solutions requiring complex nesting of tools/functions.

### Changed

- Added an example on how to invoke the `explain()` method to return a chatty answer in the `calculator` cookbook.
