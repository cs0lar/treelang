import asyncio
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from mcp.client.sse import sse_client
from starlette.requests import Request
from starlette.routing import Mount, Route

from treelang.ai.arborist import OpenAIArborist


async def main():
    server_params = StdioServerParameters(
        command="python", args=["/home/cs0lar/AI/treelang/calculator.py"], env=None
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            arborist = OpenAIArborist(model="gpt-4o-2024-11-20", session=session)
            print("Querying the arborist...")
            response = await arborist.eval("Can you calculate sqrt((25+10)*4)+3^2 - 8?")
            print(f"sqrt((25+10)*4)+3^2 - 8 = {response.content}")
            response = await arborist.eval("What is (15/3)+(2^4-6)*(9-5)?")
            print(f"(15/3)+(2^4-6)*(9-5) = {response.content}")
            response = await arborist.eval(
                "Please help me compute this expression (50-8)/2 + sqrt(64) * 3^2"
            )
            print(f"(50-8)/2 + sqrt(64) - 3^2 = {response.content}")
            response = await arborist.eval("is (7^2 - 10)/5 + sqrt(49) * (6-2) > 30?")
            print(f"(7^2 - 10)/5 + sqrt(49) * (6-2) > 30? = {response.content}")


if __name__ == "__main__":
    asyncio.run(main())
