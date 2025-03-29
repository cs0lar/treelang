from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator", debug=False)


@mcp.tool()
def add(a: str | float, b: str | float) -> str:
    return float(a) + float(b)


@mcp.tool()
def subtract(a: str | float, b: str | float) -> str:
    return float(a) - float(b)


@mcp.tool()
def multiply(a: str | float, b: str | float) -> str:
    return float(a) * float(b)


@mcp.tool()
def divide(a: str | float, b: str | float) -> str:
    if float(b) == 0:
        raise ValueError("Cannot divide by zero.")

    return float(a) / float(b)


@mcp.tool()
def power(a: str | float, b: str | float) -> str:
    return float(a) ** float(b)


@mcp.tool()
def sqrt(a: str | float) -> str:
    a = float(a)

    if a < 0:
        raise ValueError("Cannot take square root of a negative number.")

    return a**0.5


if __name__ == "__main__":
    mcp.run(transport="stdio")
