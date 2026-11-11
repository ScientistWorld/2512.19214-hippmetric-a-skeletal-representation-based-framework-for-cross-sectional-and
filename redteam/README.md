# Audit replay

Completed: 23 hidden-test invocations in two bundled CPU jobs. Findings and interpretation are in [REDTEAM.md](../REDTEAM.md). Every variant and shortcut has its own `run.sh` and retained raw train/test scores plus `status.json`. The two intentionally failing hidden tests additionally retain `failure.txt`; their leftover score files are evidence, not valid scores.

Run computation only through the gym job mechanism. Inside its container, from the workspace root, a case is replayed with:

```bash
bash redteam/shortcut_copy_surface/run.sh
```

The complete bundle is `python redteam/harness.py all`, followed by the lightweight `python redteam/analyze.py` to rebuild aggregate reports. Cases share `candidate.py` and `harness.py`; the harness installs candidate code into `method/`, runs the artifact producer to completion, runs visible train evaluation, then invokes the unchanged hidden test as `bash scripts/evaluate_test.sh` with no arguments in a separate process. Candidates only use scientist-visible files. No hidden evaluator code is imported into them.

The harness snapshots original candidate-editable state in ignored `redteam/runtime/`, restores it between cases and in a `finally` block, and reuses generated reference outputs to avoid repeated fitting for output-only shortcuts. Missing reference/baseline artifacts are regenerated from the visible implementations. Full method seed runs are independently recomputed. The original method source and rank coefficients are recorded in `reference/`; the original revision and job launcher are recorded in `original/`.

`rank_summary.json` is a diagnostic application of experiment weights, absolute coefficient magnitudes and metric directions, using population SD across the listed successful audit attempts. It is not an observed future leaderboard: future attempts change the normalization population. Failed tests have no valid rank even where a diagnostic number can be computed from a stale score file. NaN-skipping is conditional, not an asserted downstream policy. `seed_spread.json` compares the three full method reruns on the fixed dataset.

Generated arrays, runtime caches and full logs are ignored by `redteam/.gitignore`. Small raw scores, status records, failure evidence, selection diagnostics and enumeration diagnostics are committed. The audit leaves gym source/data/evaluator/scoring files restored to the original revision, apart from the required root action protocol.
