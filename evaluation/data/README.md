# Evaluation datasets

Datasets are versioned by directory. `v1/offline.json` contains deterministic
cases executed in normal CI without credentials. `v1/live.jsonl` contains the
credentialed model questions retained for a later scheduled/manual workflow.

Published benchmark results must record the dataset version and must not compare
results from different versions as if they used the same cases.
