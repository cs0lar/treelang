# Evaluation

Run the deterministic offline benchmark without credentials or network access:

```sh
uv run python evaluation/eval.py --output evaluation-results/offline.json
```

The command exits with status 0 only when every case passes. Its JSON output
records dataset version, parse/schema/execution/correctness status, required AST
construct usage, latency, token and cost placeholders, model/provider identity,
and categorized failures. Offline token counts and estimated cost are zero by
definition.

Datasets live under versioned directories in `evaluation/data/`. Add or change a
case by creating a new dataset version so benchmark results remain comparable.
The credentialed questions in `data/v1/live.jsonl` are intentionally excluded
from normal CI until a manual/scheduled live workflow is introduced.
