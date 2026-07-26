"""Command-line entry point for credentialed live-model evaluation."""

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Literal

from evaluation.dataset import (
    DEFAULT_LIVE_DATASET_PATH,
    DEFAULT_LIVE_DATASET_VERSION,
    load_live_dataset,
)
from evaluation.live import LiveBenchmarkRunner
from evaluation.offline import OfflineToolProvider
from treelang.ai.anthropic import AnthropicTransport
from treelang.ai.arborist import OpenAIArborist
from treelang.ai.config import ArboristConfig
from treelang.ai.transport import OpenAITransport

type ProviderName = Literal["openai", "anthropic"]
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_LIVE_DATASET_PATH)
    parser.add_argument("--dataset-version", default=DEFAULT_LIVE_DATASET_VERSION)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--provider",
        choices=("openai", "anthropic"),
        default="openai",
    )
    parser.add_argument("--model")
    parser.add_argument("--input-cost-per-million", type=float, default=0.0)
    parser.add_argument("--output-cost-per-million", type=float, default=0.0)
    return parser.parse_args()


async def run(
    *,
    dataset_path: Path,
    dataset_version: str,
    output_path: Path,
    model: str | None,
    provider_name: ProviderName = "openai",
    input_cost_per_million: float,
    output_cost_per_million: float,
) -> int:
    dataset = load_live_dataset(dataset_path, version=dataset_version)
    config, transport = create_model_runtime(provider_name, model)
    tool_provider = OfflineToolProvider()
    arborist = OpenAIArborist(
        model=config.model,
        provider=tool_provider,
        config=config,
        transport=transport,
    )
    result = await LiveBenchmarkRunner(
        arborist,
        transport,
        provider_name=provider_name,
        input_cost_per_million=input_cost_per_million,
        output_cost_per_million=output_cost_per_million,
    ).run(dataset)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{result.model_dump_json(indent=2)}\n", encoding="utf-8")
    print(
        f"Live evaluation v{result.dataset_version}: "
        f"{result.passed}/{result.total} passed ({result.pass_rate:.1%})"
    )
    return 0 if result.passed == result.total else 1


def create_model_runtime(
    provider: ProviderName,
    model: str | None,
) -> tuple[ArboristConfig, OpenAITransport | AnthropicTransport]:
    """Create one provider transport from provider-specific environment values."""
    if provider == "openai":
        config = ArboristConfig.from_env(model)
        return config, OpenAITransport(
            api_key=config.api_key,
            timeout=config.timeout,
        )
    if provider == "anthropic":
        selected_model = (
            model or os.getenv("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL
        )
        timeout_value = os.getenv("ANTHROPIC_TIMEOUT")
        timeout = float(timeout_value) if timeout_value else None
        config = ArboristConfig(model=selected_model, timeout=timeout)
        return config, AnthropicTransport(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            timeout=timeout,
        )
    raise ValueError(f"Unsupported model provider '{provider}'")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = parse_args()
    return asyncio.run(
        run(
            dataset_path=arguments.dataset,
            dataset_version=arguments.dataset_version,
            output_path=arguments.output,
            model=arguments.model,
            provider_name=arguments.provider,
            input_cost_per_million=arguments.input_cost_per_million,
            output_cost_per_million=arguments.output_cost_per_million,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
