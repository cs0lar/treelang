# Changelog

## [0.5.0] - 2025-05-11

### Added
- `TreeConditional` node for support of `if-then-else` conditionals in `treelang`.

### Changed
- Added conditionals support in `AST` parsing, evaluating, visiting and representing (`repr()`)
- Added conditional node tests.
- Added conditional example to `Evaluator`.
- Added example of query with conditional in `calculator.ipynb` cookbook.
- Added `greater_than` tool in `calculator.py`.

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
- Removed the *release branch* section from `CONTRIBUTING.md`.

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