# Changelog

## [Unreleased]

### Added

- Added a supported package-level API and domain-specific exception hierarchy.
- Added explicit handling for structured, textual, empty, non-text, and error MCP results.
- Added a tag-validated release pipeline with isolated artifact smoke tests,
  generated release notes, build provenance, and PyPI Trusted Publishing.

### Changed

- Compiled AST tool signatures now use deterministic duplicate parameter names without mutating the source tree.
- Tool execution validates provider definitions and parameter counts before invocation.

### Removed

- Removed the undocumented, conditionally defined `LlamIndexToolProvider`, which depended on an undeclared optional package and could not execute successfully.

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
