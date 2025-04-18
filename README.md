# `treelang`

`treelang` uses Abstract Syntax Trees (ASTs) for advanced function calling with Large Language Models (LLMs), i.e. function-calling on steroids! 

## Why `treelang`

- **Complex worflows/function nesting**: Primarily `treelang` was created as a practical way to support arbitrarily complex function-calling workflows, where the answer to a question may involve multiple steps each with its own multiple dependencies.
- **Cost Saving**: With `treelang` you avoid the typical function-calling loop whereby the LLM outputs a function call, your program evaluates it and returns the result back to the LLM for this cycle to repeat until the final result is computed. `treelang` generates the AST for the full solution using a single call to the underlying LLM!
- **Security**: `treelang` deals with ASTs which means it never needs to know the result from any node in the tree, which may be sensitive (e.g. "my patients email addresses"). The developer can focus on the reliability and security of the underlying tools that will be used to evaluate the AST. 
- **Portability**: `treelang` "packages" solutions into ASTs which means that solutions can be easily reused, shared, cached and interpreted.
- **Automated solutions generator**: *coming soon...*


## Features

- **Abstract Syntax Tree Representation**: `treelang` speaks Trees.
- **MCP Client**: `treelang` is an [MCP client](https://modelcontextprotocol.io/introduction) out of the box. 
- **LLM Integration**: Use LLMs (e.g., OpenAI models) to generate ASTs.
- **Tool Selection**: Dynamically select tools (functions) available in the system.
- **Asynchronous Execution**: Fully asynchronous design for efficient computation.

## Installation

  ```bash
   pip install treelang
  ```


## Resources

- **Cookbooks**: Play with the *Jupiter Notebooks* in the `cookbook` directory to learn more about `treelang`.  