"""Command-line entry point for the deterministic offline benchmark."""

import argparse
import asyncio
import logging
from pathlib import Path

from evaluation.comparison import RegressionTolerances, compare_results
from evaluation.dataset import DEFAULT_DATASET_PATH, load_dataset
from evaluation.models import BenchmarkResult
from evaluation.offline import OfflineToolProvider
from evaluation.runner import OfflineBenchmarkRunner

DEFAULT_BASELINE_PATH = Path(__file__).parent / "baselines" / "v1" / "offline.json"
DEFAULT_TOLERANCES_PATH = Path(__file__).parent / "baselines" / "v1" / "tolerances.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--tolerances", type=Path, default=DEFAULT_TOLERANCES_PATH)
    parser.add_argument("--comparison-output", type=Path)
    return parser.parse_args()


async def main(
    dataset_path: Path,
    output_path: Path | None = None,
    baseline_path: Path = DEFAULT_BASELINE_PATH,
    tolerances_path: Path = DEFAULT_TOLERANCES_PATH,
    comparison_output_path: Path | None = None,
) -> int:
    dataset = load_dataset(dataset_path)
    result = await OfflineBenchmarkRunner(OfflineToolProvider()).run(dataset)
    payload = result.model_dump_json(indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{payload}\n", encoding="utf-8")
    baseline = BenchmarkResult.model_validate_json(
        baseline_path.read_text(encoding="utf-8")
    )
    tolerances = RegressionTolerances.model_validate_json(
        tolerances_path.read_text(encoding="utf-8")
    )
    comparison = compare_results(baseline, result, tolerances)
    if comparison_output_path is not None:
        comparison_output_path.parent.mkdir(parents=True, exist_ok=True)
        comparison_output_path.write_text(
            f"{comparison.model_dump_json(indent=2)}\n", encoding="utf-8"
        )
    print(
        f"Offline evaluation v{result.dataset_version}: "
        f"{result.passed}/{result.total} passed ({result.pass_rate:.1%})"
    )
    if not comparison.passed:
        print(f"Regression comparison failed with {len(comparison.issues)} issue(s).")
    return 0 if result.passed == result.total and comparison.passed else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = parse_args()
    raise SystemExit(
        asyncio.run(
            main(
                arguments.dataset,
                arguments.output,
                arguments.baseline,
                arguments.tolerances,
                arguments.comparison_output,
            )
        )
    )
