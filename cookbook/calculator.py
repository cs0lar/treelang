from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator", debug=False)


@mcp.tool()
def add(a: float, b: float) -> str:
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero.")

    return a / b


@mcp.tool()
def power(a: float, b: float) -> float:
    return a**b


@mcp.tool()
def greater_than(a: float, b: float) -> bool:
    return a > b


@mcp.tool()
def sqrt(a: float) -> float:
    a = float(a)

    if a < 0:
        raise ValueError("Cannot take square root of a negative number.")

    return a**0.5


if __name__ == "__main__":
    mcp.run(transport="stdio")
