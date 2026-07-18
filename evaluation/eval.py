"""Command-line entry point for the deterministic offline benchmark."""

import argparse
import asyncio
from pathlib import Path

from evaluation.dataset import DEFAULT_DATASET_PATH, load_dataset
from evaluation.offline import OfflineToolProvider
from evaluation.runner import OfflineBenchmarkRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


async def main(dataset_path: Path, output_path: Path | None = None) -> int:
    dataset = load_dataset(dataset_path)
    result = await OfflineBenchmarkRunner(OfflineToolProvider()).run(dataset)
    payload = result.model_dump_json(indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{payload}\n", encoding="utf-8")
    print(
        f"Offline evaluation v{result.dataset_version}: "
        f"{result.passed}/{result.total} passed ({result.pass_rate:.1%})"
    )
    return 0 if result.passed == result.total else 1


if __name__ == "__main__":
    arguments = parse_args()
    raise SystemExit(asyncio.run(main(arguments.dataset, arguments.output)))
