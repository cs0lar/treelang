import asyncio
import json
import logging
import os
import signal
import threading
import traceback
from pathlib import Path

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.server.fastmcp import FastMCP

from evaluation.data.tools import tools as tool_list
from treelang.ai.arborist import EvalType, OpenAIArborist
from treelang.ai.provider import MCPToolProvider

logger = logging.getLogger(__name__)
mcp = FastMCP("evaluator", debug=False)


class Evaluator:
    def __init__(self, provider: MCPToolProvider):
        self.arborist = OpenAIArborist(
            model="gpt-4.1",
            provider=provider,
        )

    async def evaluate(self):
        passed = 0
        path = Path(__file__).parent / "data" / "questions.jsonl"
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        [mcp.add_tool(tool) for tool in tool_list]

        for i, row in enumerate(rows):
            try:
                question = row["q"]
                answer = row.get("a", "")
                must_use = row.get("must_use", [])
                response = await self.arborist.eval(question, EvalType.WALK)
                actual = response.content
                ok = answer == actual

                for needle in must_use:
                    if needle.lower() not in json.dumps(response.jsontree).lower():
                        logger.warning(
                            f"Missing required tool usage '{needle}' in response."
                        )
                        ok = False
                logger.info(
                    f"\n#{i + 1} Query: {question}\nExpected: {answer}\nActual: {actual}\nOK={ok}\n"
                )
                passed += 1 if ok else 0
            except Exception as e:
                logger.error(f"Error evaluating question #{i}: {e}")
                traceback.print_exc()
                continue
        return passed, len(rows)


async def main():
    # instantiate the MCP server with the SSE transport
    logger.debug("Starting MCP server with SSE transport")
    # create a new SSE client and connect to the server
    stream_ctxt = sse_client(
        url=f"http://localhost:{mcp.settings.port}{mcp.settings.sse_path}"
    )
    (read, write) = await stream_ctxt.__aenter__()
    session_ctxt = ClientSession(read, write)
    session = await session_ctxt.__aenter__()
    provider = MCPToolProvider(session)
    await session.initialize()
    # run the evaluation
    evaluator = Evaluator(provider)
    passed, total = await evaluator.evaluate()
    logger.info(f"Passed {passed} out of {total} questions.")

    # close the session
    await session_ctxt.__aexit__(None, None, None)
    await stream_ctxt.__aexit__(None, None, None)


if __name__ == "__main__":
    # Start the MCP server in a background thread
    server_thread = threading.Thread(
        target=mcp.run, kwargs={"transport": "sse"}, daemon=True
    )
    server_thread.start()
    asyncio.run(main())

    # terminate the server
    os.kill(os.getpid(), signal.SIGINT)
