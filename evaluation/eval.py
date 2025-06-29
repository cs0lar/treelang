import logging
import os
import signal
import time
import asyncio
import json
from typing import Any, List, Dict
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.client.sse import sse_client
from mcp import ClientSession
from treelang.ai.provider import MCPToolProvider
from treelang.ai.arborist import EvalType, OpenAIArborist
from evaluation.data.nested import (
    tools as nested_T,
    questions as nested_Q,
    answers as nested_A,
)
from treelang.trees.tree import AST
import threading

mcp = FastMCP("evaluator", debug=False)

logger = logging.getLogger(__name__)


class CustomLoggingFormatter(logging.Formatter):
    """
    Courtesy of: https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
    """

    green = "\033[92m"
    yellow = "\033[93m"
    red = "\033[91m"
    bold_red = "\033[1m\033[91m"
    reset = "\033[0m"
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: green + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


if not logger.handlers:
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(CustomLoggingFormatter())
    logger.addHandler(ch)


def is_match_nested(expected: Any, actual: Any) -> bool:
    """
    Recursively checks if the expected and actual values match.

    Args:
        expected (Any): The expected value or structure.
        actual (Any): The actual value or structure to compare against.

    Returns:
        bool: True if the expected and actual values match, False otherwise.
    """
    if type(expected) is list:
        assert str(expected) == str(actual), f"{str(actual)} != {str(expected)}"
    else:
        expected_keys = expected.keys()

        for k in expected_keys:
            assert k in actual, f"{k} not in {actual}"

            expected_arguments = expected[k]
            actual_arguments = actual[k]

            if type(expected_arguments) is list:
                expected_arguments.sort()
                expected_param_value = str(
                    [v for v in expected_arguments if v is not None]
                )
                actual_arguments.sort()

                assert (
                    str(actual_arguments) == expected_param_value
                ), f"{str(actual_arguments)} != {expected_param_value}"
            else:
                for param, val in expected_arguments.items():
                    is_match_nested(val, actual_arguments[param])

    return True


class Evaluator:
    def __init__(self, provider):
        self.arborist = OpenAIArborist(
            model="gpt-4o-2024-11-20",
            provider=provider,
        )
        self.num_tests = 0
        self.num_passed = 0
        self.elapsed_time = 0

    async def _eval_loop(
        self,
        tools: List[Callable],
        questions: List[Dict],
        answers: List[Dict],
        test: Callable[[Any, Any], bool],
    ):
        """
        Evaluates a set of questions using provided dummy tools and a test function.
        This method loops through the questions, evaluates them using the `arborist.eval`
        method, and compares the results against expected answers using the given `test` function.

        Args:
            tools (List[Callable]): A list of callable tools to be added to the MCP server.
            questions (List[Dict]): A list of dictionaries containing questions to be evaluated.
                                    Each dictionary should have a "question" key.
            answers (List[Dict]): A list of dictionaries containing the expected answers,
                                  corresponding to the questions.
            test (Callable[[Any, Any], bool]): A function that takes the expected and actual
                                               results and returns a boolean indicating
                                               whether the test passed.
        Returns:
            Tuple[int, int]: A tuple containing the total number of tests and the number of
                             tests that passed.
        Raises:
            Exception: Logs any exceptions that occur during the evaluation of a question.
        Notes:
            - The `arborist.eval` method is used to evaluate the questions.
            - The `AST.repr` method is used to convert the response content into a string
              representation of the abstract syntax tree, which is then parsed as JSON.
            - Errors during evaluation are logged but do not interrupt the loop.
        """
        tests = len(questions)
        passed = 0

        # add tools to the MCP server
        [mcp.add_tool(tool) for tool in tools]

        for idx, question in enumerate(questions):
            expected = answers[idx]

            try:
                # evaluate the question
                response = await self.arborist.eval(question, EvalType.TREE)
                treestr = AST.repr(response.content)
                actual = json.loads(treestr)

                if test(expected, actual):
                    passed += 1

            except Exception as e:
                logger.error(f"Error evaluating question {idx}: {e}")

        return tests, passed

    async def evaluate(self):
        """
        Asynchronously evaluates answers from the `Arborist` to a set of test questions.
        It returns simple statistics about the evaluation process.
        Returns:
            None: Updates the instance's attributes `num_tests`, `num_passed`, and `elapsed_time`.
        Attributes Updated:
            num_tests (int): Total number of tests evaluated.
            num_passed (int): Total number of tests that passed.
            elapsed_time (float): Total time taken for all evaluations.
        Notes:
            - The evaluation process is performed asynchronously.
            - The `_eval_loop` method is expected to return two numbers: `tests` and `passed`
              respectively the number of tests and the number of tests that passed.
        """
        start_time = time.time()

        tests, passed = await self._eval_loop(
            tools=nested_T,
            questions=nested_Q,
            answers=nested_A,
            test=is_match_nested,
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        self.num_tests += tests
        self.num_passed += passed
        self.elapsed_time += elapsed_time

    def log_results(self):
        """
        Logs the results of the evaluation process, including the total number of tests run,
        the number of tests passed, the pass percentage, and the total elapsed time.

        This method uses the logger to output the following information:
        - Total tests run
        - Total tests passed
        - Pass percentage (calculated as the ratio of passed tests to total tests, expressed as a percentage)
        - Total elapsed time in seconds
        """
        logger.info(f"Total tests run: {self.num_tests}")
        logger.info(f"Total tests passed: {self.num_passed}")
        logger.info(f"Pass percentage: {(self.num_passed / self.num_tests) * 100:.2f}%")
        logger.info(f"Total elapsed time: {self.elapsed_time:.2f} seconds")


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
    await evaluator.evaluate()
    evaluator.log_results()

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
