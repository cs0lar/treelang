# 🌲 `treelang`

![PyPI - Version](https://img.shields.io/pypi/v/treelang?label=pypi%20package&color=green)
[![PyPI Downloads](https://static.pepy.tech/badge/treelang)](https://pepy.tech/projects/treelang)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Turn your toolboxes into executable **Abstract Syntax Trees** (ASTs) that Large Language Models can plan in a single shot. `treelang` lets you express arbitrarily complex workflows, keep sensitive values out of the LLM, and reuse the resulting programs as shareable, cacheable trees.

## Highlights

- **One LLM call, full plan** – generate an AST for a complete solution without the expensive function-call loop.
- **Complex workflows** – conditionals, higher-order functions (`map`, `filter`, `reduce`), and nested tool invocations all live in one tree.
- **Secure + green** – the LLM never sees tool results; you evaluate nodes locally while controlling cost and compliance.
- **Model Context Protocol native** – ships with an MCP client provider but can work with any tool registry through the `ToolProvider` abstraction.
- **Composable outputs** – turn ASTs into callable tools (`AST.tool`) or serialize/describe them for sharing, caching, or review.

## What you can build

- **Enterprise copilots** that must orchestrate dozens of tools with branching logic.
- **Automations** that need to fan out over datasets (e.g., score/map/filter large collections asynchronously).
- **Reusable skills**: persist an AST, describe it with `EvalResponse.describe()`, and redeploy it as a tool on your MCP server.
- **LLM evaluation loops**: ask for the tree (`EvalType.TREE`) to inspect reasoning before execution, or walk it immediately for answers.

## Quick start

### Requirements

- Python 3.12+
- An OpenAI API key (`OPENAI_API_KEY`) and optional `OPENAI_MODEL` override (defaults to `gpt-4o-2024-11-20`)
- A source of tools: an MCP server, or your own provider implementing `treelang.ai.provider.ToolProvider`

### Install

```bash
pip install treelang
```

### Wire up tools (MCP)

```python
import asyncio
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from treelang.ai.arborist import EvalType, OpenAIArborist
from treelang.ai.provider import MCPToolProvider


async def build_arborist(stack: AsyncExitStack) -> OpenAIArborist:
    try:
        await stack.__aenter__()
        # Connect to a streamable HTTP server
        read_stream, write_stream, _ = await stack.enter_async_context(
            streamable_http_client("http://localhost:8000/mcp")
        )

        # Create a session using the client streams
        session = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        # Initialize the connection
        await session.initialize()

        # Create the Arborist
        provider = MCPToolProvider(session)
        arborist = OpenAIArborist(provider=provider, model="gpt-4o")

        return arborist

    except Exception:
        print ("Error building the Arborist")
        await stack.aclose()
        raise

```

### Ask a question (MCP)

```python
async def run():
    stack = AsyncExitStack()
    arborist = await build_arborist(stack)

    response = await arborist.eval(
        query="Compare next weekend flights BOS➜SFO and summarize the cheapest option.",
        type=EvalType.WALK,  # change to EvalType.TREE to inspect the JSON AST instead
    )
    print(response.content)  # fully-evaluated tool output
    if (stack):
        await stack.aclose()

if __name__ == "__main__":
    asyncio.run(run())
```

Use `response.jsontree` with `AST.parse()` or `AST.repr()` if you want to log, cache, or transform the raw tree.

## Tree-first workflow

1. **Generate** – `OpenAIArborist` assembles an AST using your available tools.
2. **Inspect** – represent the tree as JSON, describe it with `EvalResponse.describe()`, or pretty-print it using `AST.repr()`.
3. **Evaluate** – `AST.eval(tree, provider)` asynchronously executes every node; the LLM never sees intermediate values.
4. **Package** – `await AST.tool(tree, provider)` turns a tree into a callable tool so you can add it back to your MCP server.

## Architecture at a glance

- **Arborist (`treelang/ai/arborist.py`)** – orchestrates LLM calls, maintains history via the optional `Memory` interface, and decides whether to return ASTs or walked results.
- **Tool providers (`treelang/ai/provider.py`)** – abstract how tools are discovered/invoked. We ship an MCP client implementation and a template for custom providers.
- **Selectors (`treelang/ai/selector.py`)** – plug in your own tool filtering logic; `AllToolsSelector` ships by default.
- **Trees (`treelang/trees/tree.py`)** – immutable node classes plus helpers such as async traversal, repr generation, and turning trees into callable tools.

## Resources & examples

- **Cookbook notebooks** (`cookbook/`) walk through building trees, call patterns, and evaluation strategies.
- **Evaluation harness** (`evaluation/eval.py`) stress-tests tree generation using curated toolsets and questions; great for regression testing.
- **Unit tests** (`tests/`) cover the AST core and are a good reference for expected behavior when extending nodes.

## Contributing & local development

We actively welcome contributions—see [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.



