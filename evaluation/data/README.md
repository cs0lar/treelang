# Evaluation datasets

Datasets are versioned by directory. `v1/offline.json` contains deterministic
cases executed in normal CI without credentials. `v1/live.jsonl` preserves the
original credentialed model questions. `v2/live.jsonl` is the current manual
live benchmark and strengthens the required currency-tool composition.

Published benchmark results must record the dataset version and must not compare
results from different versions as if they used the same cases.
