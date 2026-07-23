"""Load and validate versioned evaluation datasets."""

from pathlib import Path

from evaluation.models import (
    EvaluationDataset,
    LiveEvaluationCase,
    LiveEvaluationDataset,
)

DEFAULT_DATASET_PATH = Path(__file__).parent / "data" / "v1" / "offline.json"
DEFAULT_LIVE_DATASET_VERSION = "2.0"
DEFAULT_LIVE_DATASET_PATH = Path(__file__).parent / "data" / "v2" / "live.jsonl"


def load_dataset(path: Path = DEFAULT_DATASET_PATH) -> EvaluationDataset:
    """Load a UTF-8 JSON dataset with Pydantic validation."""
    return EvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))


def load_live_dataset(
    path: Path = DEFAULT_LIVE_DATASET_PATH,
    *,
    version: str = DEFAULT_LIVE_DATASET_VERSION,
) -> LiveEvaluationDataset:
    """Load a versioned JSON Lines dataset for credentialed model evaluation."""
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(LiveEvaluationCase.model_validate_json(line))
    return LiveEvaluationDataset(version=version, cases=cases)
