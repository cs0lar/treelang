# Changelog

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