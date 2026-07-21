from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator", debug=False)


@mcp.tool(structured_output=False)
def add(a: float, b: float) -> float:
    return a + b


@mcp.tool(structured_output=False)
def subtract(a: float, b: float) -> float:
    return a - b


@mcp.tool(structured_output=False)
def multiply(a: float, b: float) -> float:
    return a * b


@mcp.tool(structured_output=False)
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero.")

    return a / b


@mcp.tool(structured_output=False)
def power(a: float, b: float) -> float:
    return a**b


@mcp.tool(structured_output=False)
def greater_than(a: float, b: float) -> bool:
    return a > b


@mcp.tool(structured_output=False)
def sqrt(a: float) -> float:
    a = float(a)

    if a < 0:
        raise ValueError("Cannot take square root of a negative number.")

    return a**0.5


if __name__ == "__main__":
    mcp.run(transport="stdio")
