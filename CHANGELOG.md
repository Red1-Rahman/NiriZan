# Changelog

All notable changes to NiriZan are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While NiriZan is on a `0.x` version, breaking changes are reflected in a
**minor** version bump (`0.1.0 → 0.2.0`), per the Versioning Rule in
[`docs/contracts.md`](docs/contracts.md#versioning-rule-for-this-document); the
jump to `1.0.0` is reserved for the point the public contract surface is
considered stable.

## [0.3.0] - drafted for release

### Added

- Statistical attribution in `AttributionEngine.analyze()` using bootstrap confidence intervals and Mann-Whitney U tests instead of raw mean-difference thresholds.
- Holm-Bonferroni correction across the judge-drift and system-drift hypotheses.
- Explicit small-sample behavior: when either comparison group has fewer than 5 observations, Mann-Whitney U is skipped and attribution relies on bootstrap confidence intervals.
- Configurable statistical parameters for attribution: `alpha`, `confidence_level`, `n_bootstrap`, and optional `seed`.
- Statistical method and evidence details in attribution explanations, including deltas, methods, p-values, and correction status.

### Changed

- **Breaking:** Replaced the `AttributionEngine` `significance_threshold` parameter with `alpha`, reflecting that attribution now uses statistical significance rather than a raw score-difference threshold.
- `AttributionEngine` now distinguishes judge drift using a two-sided statistical test, while system drift specifically tests for a statistically supported decrease in candidate scores.
- Drift decisions now require statistical evidence rather than treating an absolute mean-score delta of `significance_threshold` as sufficient evidence.
- `AttributionEngine` now applies Holm-Bonferroni correction across the judge and system hypotheses before classifying statistically significant drift.
- `AttributionEngine` reuses the centralized statistical helpers in `nirizan.metrics.stats` rather than maintaining attribution-specific statistical implementations.
- `DriftAttribution.NONE` explanations now report the statistical decision methodology instead of describing a raw threshold comparison as "statistically significant."
- Existing `DriftAttribution` states and downstream attribution fields remain unchanged.

### Fixed

- Removed the misleading use of `significance_threshold` as a proxy for statistical significance in `AttributionEngine.analyze()`.
- Prevented attribution from classifying drift solely from the magnitude of a mean-score difference without considering distributional evidence.
- Explicitly handled insufficient sample sizes by avoiding Mann-Whitney U when either comparison group has fewer than 5 observations.
- `INCONCLUSIVE` remains reserved for invalid or unusable score inputs, keeping zero/no-change observations distinguishable from unavailable statistical evidence.

## [0.2.0] - 2026-08-28

PR #35 closes #22 and carries the required `pyproject.toml` version bump per
the Versioning Rule.

### Added

- `DriftAttribution.JOINT_DRIFT` — a verdict for when the judge-side and
  system-side score deltas both cross the significance threshold in the same
  evaluation window. Previously such cases collapsed into `JUDGE_DRIFT`,
  discarding the system-side signal.
- `DriftAttribution.INCONCLUSIVE` — a verdict for when `AttributionEngine.analyze`
  cannot evaluate its input score distributions at all (empty or containing
  non-finite values), instead of forcing an unrelated result out of unusable
  inputs.
- `JudgeReliabilityMetrics.joint_drift_rate` and `JudgeReliabilityMetrics.inconclusive_rate`
  — longitudinal rates for the two new attribution states, each with a `0.0`
  default so existing callers are unaffected.
- Health-score penalty multipliers for `JOINT_DRIFT` (`0.70`) and `INCONCLUSIVE`
  (`0.85`) in `compute_system_health_score`.
- `docs/contracts.md`: full Phase 5 contract documentation for the five-state
  `DriftAttribution` enum, `JudgeReliabilityStatus`, `JudgeReliabilityMetrics`,
  and `DashboardSnapshot`.
- This `CHANGELOG.md`.

### Changed

- **Breaking:** `JudgeReliabilityMetrics.judge_drift_rate` and `system_drift_rate`
  now include `JOINT_DRIFT` verdicts in their counts. `judge_drift_rate` was
  previously "fraction of verdicts where `attribution == JUDGE_DRIFT`"; it is
  now "fraction where `attribution` is `JUDGE_DRIFT` **or** `JOINT_DRIFT`"
  (and correspondingly for `system_drift_rate` with `SYSTEM_DRIFT`). A verdict
  window summarized before and after this change can produce different rates
  for the same underlying data. See the **Phase 5 (post-launch) — Breaking
  Change** section of `docs/contracts.md` for the full migration note;
  historical `JudgeReliabilityMetrics` snapshots remain valid as-is and do not
  need to be recomputed.
- `compute_judge_reliability` now excludes `INCONCLUSIVE` verdicts from
  `mean_judge_score_delta` and `judge_score_delta_std`. `AttributionEngine.analyze`
  reports a `0.0` delta on `INCONCLUSIVE` verdicts as a "not measured"
  placeholder, not an observation of zero drift; including it previously
  biased both statistics toward zero. `INCONCLUSIVE` verdicts are still
  reflected in `verdict_count`, `inconclusive_rate`, and `flagged_verdicts`.
- `docs/architecture.md`: updated the Trust & Attribution Layer description
  from a three-state to a five-state verdict.
- `docs/contracts.md`: clarified that `SYSTEM_DRIFT`/`JOINT_DRIFT` require the
  system-side delta to be a **drop** (`system_score_delta < 0` and past the
  significance threshold), unlike `JUDGE_DRIFT`, which fires on a shift past
  the threshold in either direction.

### Fixed

- **`validate_scores`, `bootstrap_delta_ci`, and `mann_whitney_regression` had
  independently maintained duplicate implementations in
  `regression/thresholds.py`, `metrics/statistical_gating.py`, and (for
  `bootstrap_delta_ci`) `gate/verdict.py`, with different validation
  behavior on the same inputs** (#23): the `regression/thresholds.py`
  copy of `validate_scores` rejected non-1D input while the
  `metrics/statistical_gating.py` copy did not; the `statistical_gating.py`
  copy of `mann_whitney_regression` required at least 5 observations per
  group while the `thresholds.py` copy had no minimum; and the
  `gate/verdict.py` copy of `bootstrap_delta_ci` rejected `n_bootstrap < 1`
  with no score finiteness/range check, while the `statistical_gating.py`
  copy validated score finiteness/range but not `n_bootstrap`. Each copy's
  own tests only exercised its own historical behavior, so the divergence
  went undetected. Fixed by consolidating all four helpers into a single
  authoritative implementation in `src/nirizan/metrics/stats.py`, which
  every caller now delegates to; backwards-compatible aliases
  (`calculate_bootstrap_ci`, `compute_holm_bonferroni`, `compute_mann_whitney_u`)
  are re-exported from `nirizan.metrics` for existing callers, and tests
  (`tests/metrics/test_stats.py`) now exercise the previously-divergent
  edge cases explicitly (#33).

- `compute_judge_reliability` now raises `ValueError` on a verdict window
  where every verdict is `INCONCLUSIVE`, rather than silently computing delta
  statistics with no real observations behind them.
- Removed an unused `compute_system_health_score` import from
  `tests/integration/test_end_to_end.py`.
- Added missing assertions in `tests/trust/test_attribution.py` confirming
  `system_score_delta == 0.0` and `judge_score_delta == 0.0` on `INCONCLUSIVE`
  verdicts, per the contract's placeholder-delta guarantee.

## [0.1.0] - 2026-08-11

Initial public release of NiriZan, an open-source continuous evaluation
infrastructure and Python framework for production AI systems. First
available via PyPI on 2026-08-11; the corresponding GitHub Release was
published on 2026-08-23.

### Added

- Trace instrumentation and collection.
- RAG Triad evaluation: Context Relevance, Groundedness, Answer Relevance.
- LLM-as-Judge evaluation.
- Statistical regression detection.
- Judge reliability and drift detection (three-state: `NONE`, `SYSTEM_DRIFT`,
  `JUDGE_DRIFT`).
- Experiment tracking and baseline management.
- Deployment-aware CI/CD quality gates.
- Typed Pydantic contracts between components (`docs/contracts.md`).
- Security-focused CI/CD and supply-chain controls; PyPI publishing via
  GitHub Actions Trusted Publishing.

[Unreleased]: https://github.com/Red1-Rahman/NiriZan/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Red1-Rahman/NiriZan/releases/tag/v0.1.0
