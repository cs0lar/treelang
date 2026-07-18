"""Load and validate versioned evaluation datasets."""

from pathlib import Path

from evaluation.models import EvaluationDataset

DEFAULT_DATASET_PATH = Path(__file__).parent / "data" / "v1" / "offline.json"


def load_dataset(path: Path = DEFAULT_DATASET_PATH) -> EvaluationDataset:
    """Load a UTF-8 JSON dataset with Pydantic validation."""
    return EvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))
