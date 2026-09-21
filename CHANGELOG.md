# Changelog

All notable changes to NiriZan are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While NiriZan is on a `0.x` version, breaking changes are reflected in a
**minor** version bump (`0.1.0 → 0.2.0`), per the Versioning Rule in
[`docs/contracts.md`](docs/contracts.md#versioning-rule-for-this-document); the
jump to `1.0.0` is reserved for the point the public contract surface is
considered stable.

## [0.4.0] - 2026-09-20

This release adds a second, multivariate track to regression detection. It catches changes in how metrics vary together (variance and correlation shifts) that the per-metric comparator cannot see. It contains two breaking changes and a license change; see **Changed**.

### Added

- **Multivariate structure track** (`nirizan.regression.multivariate`). `MultivariateComparator` compares row-aligned baseline and candidate score matrices with two permutation-calibrated tests and always returns exactly two `MultivariateVerdict` records:
  - `scale`: variance-only drift, from epsilon-floored log-variance ratios. Invariant to location shifts.
  - `dependence`: correlation-only drift, from the largest change in within-group rank correlation. Invariant to rank-preserving changes in the individual metrics. Skipped, with a `NONE` verdict, when there is only one metric.
  - Both p-values use the `(k+1)/(R+1)` convention and are combined with Holm-Bonferroni at `structure_alpha`. Both tests are undirected: they flag that structure changed, not that quality dropped.
- **Severity modes** via the frozen Pydantic model `MultivariateConfig`. `BALANCED` (default) caps severity at `WARNING`, so an undirected structure change can never block a deploy on its own. `STRICT` allows `BLOCKING` and is intended for callers who have carved the structure alpha out of the univariate comparator's budget. The default effect thresholds (`warning_effect=0.20`, `blocking_effect=0.40`) are provisional pending calibration on real data.
- **Deterministic by default.** The permutation seed is derived from `(run_id, baseline_id)`, so re-evaluating the same comparison reproduces the same verdicts. Set `MultivariateConfig.seed` to pin it.
- **Score matrices from raw results.** `ScoreMatrix.from_metric_results` pivots `MetricResult` records into a matrix, keeping complete cases only. `MultivariateComparator.compare_metric_results` wraps the whole flow and returns `INCONCLUSIVE` verdicts, with descriptive metric deltas where complete rows exist, instead of raising when data is insufficient. `compare()` on pre-built matrices raises `InsufficientDataError`.
- **Gate integration.** `evaluate_gate()` accepts an optional `multivariate_verdicts` argument and fails on `BLOCKING` from either track (reachable only in `STRICT` mode). Decision-metric selection stays univariate-only. `GateVerdict.multivariate_verdicts` is a new field that defaults to an empty list.
- **CI summary and dashboard.** The GitHub summary renders a structure-track table when multivariate verdicts exist, and omits it otherwise. `DashboardSnapshot.multivariate_verdicts` and `assemble_dashboard_snapshot(multivariate_verdicts=...)` carry the verdicts as informational context; they do not affect `compute_system_health_score`.
- **Statistical primitives** in `nirizan.metrics.stats`, also exported from `nirizan.metrics`: `scale_logvar_statistic`, `scale_logvar_test`, `dependence_max_t_statistic`, `dependence_max_t_test`, `permutation_test`, `permutation_p_value`, `validate_score_matrix`, and `cohens_d`.
- Contracts, architecture, and user manual documentation for the structure track (Phase 6).

### Changed

- **Breaking:** `nirizan.metrics.bootstrap_delta_ci` now resolves to the canonical `nirizan.metrics.stats.bootstrap_delta_ci`. It previously resolved to a 2-tuple wrapper. Differences:
  - It returns `(delta_hat, ci_lower, ci_upper)` instead of `(ci_lower, ci_upper)`.
  - The `confidence` keyword is now `confidence_level`.
  - `n_bootstrap` defaults to `10000` (was `5000`).
  - `seed` defaults to `None` (was `42`), so results vary between calls unless you pass a seed.

```python
  # 0.3.0
  ci_lower, ci_upper = bootstrap_delta_ci(candidate, baseline, confidence=0.95)

  # 0.4.0
  _, ci_lower, ci_upper = bootstrap_delta_ci(
      candidate, baseline, confidence_level=0.95, seed=42
  )

  # or keep the old behavior unchanged
  from nirizan.metrics.statistical_gating import bootstrap_delta_ci
```
- **Breaking:** `evaluate_gate()` raises `ValueError` when its verdicts do not all share one `(run_id, baseline_id)` pair. Such input was previously combined silently.
- `cohens_d` moved to `nirizan.metrics.stats`; `nirizan.regression.comparator.cohens_d` remains as a re-export.
- **License:** NiriZan is now licensed under Apache-2.0 (previously GPL-3.0-or-later). Releases 0.1.0 to 0.3.0 remain available under GPL-3.0-or-later.

### Deprecated

- The 2-tuple `bootstrap_delta_ci` wrappers in `nirizan.metrics.statistical_gating` and `nirizan.gate.verdict`. They still work and delegate to the canonical implementation, but do not yet emit a `DeprecationWarning`. New code should call the canonical function.

### Fixed

- `nirizan.__version__` reported `0.2.0` in the published 0.3.0 release.

## [0.3.0] - 2026-09-01 (PyPI date)

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
