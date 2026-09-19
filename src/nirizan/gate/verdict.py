# src/nirizan/gate/verdict.py
"""Deployment gate contracts and evaluation.

The gate consumes two streams of verdicts:

* ``RegressionVerdict`` — the univariate track's per-metric verdicts from
  ``regression.comparator.BaselineComparator``. These are the primary
  decision signal; a single univariate BLOCKING verdict fails the gate.
* ``MultivariateVerdict`` — the structure track's verdicts from
  ``regression.multivariate.MultivariateComparator``. These are an
  escalation signal only. In the default BALANCED mode the comparator
  caps their severity at WARNING, so any BLOCKING multivariate verdict
  reaching the gate is either STRICT-mode or hand-constructed; the gate
  does not re-check the mode, it trusts the severity field.

The gate's ``passed`` field flips on any BLOCKING verdict from either
track. The mode-cap that separates "structure track can only warn" from
"structure track can block" is a comparator concern, not a gate concern;
a gate that re-applied the cap would be redundant with the comparator and
would need to be kept in sync with it.

The local ``bootstrap_delta_ci`` is a deprecated 2-tuple shim around the
canonical 3-tuple ``nirizan.metrics.stats.bootstrap_delta_ci``. It is
retained for backward compatibility with the existing gate API; new code
should call the canonical function directly.
"""

from __future__ import annotations

from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from nirizan._logging import get_logger
from nirizan.metrics.stats import bootstrap_delta_ci as _stats_bootstrap_delta_ci
from nirizan.regression.comparator import (
    RegressionSeverity,
    RegressionVerdict,
)
from nirizan.regression.multivariate import MultivariateVerdict

logger = get_logger(__name__)


class GateVerdict(BaseModel):
    """Overall deployment gate result.

    ``multivariate_verdicts`` is optional and defaults to an empty list;
    callers that do not run the structure track see an empty list, and
    the field's presence on the model is a non-breaking addition. Verdicts
    carried here are informational for reporting and escalation for the
    gate; they do not participate in ``select_decision_metric`` (which is
    univariate-only and requires a ``metric_name`` field the multivariate
    verdicts do not have).
    """

    model_config = ConfigDict(strict=True)

    passed: bool
    confidence_interval: tuple[float, float]
    regression_verdicts: list[RegressionVerdict] = Field(default_factory=list)
    multivariate_verdicts: list[MultivariateVerdict] = Field(default_factory=list)
    run_id: UUID


SEVERITY_WEIGHT = {
    RegressionSeverity.BLOCKING: 3,
    RegressionSeverity.WARNING: 2,
    RegressionSeverity.NONE: 1,
}


def bootstrap_delta_ci(
    candidate: np.ndarray,
    baseline: np.ndarray,
    *,
    n_bootstrap: int = 5000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute bootstrap confidence interval for delta mean score.

    Backward-compatible 2-tuple shim around
    ``nirizan.metrics.stats.bootstrap_delta_ci``, which returns the
    canonical ``(delta_hat, ci_lower, ci_upper)`` 3-tuple. Retains the
    gate's historical argument-validation messages (its error strings are
    part of the gate's contract with its callers) and delegates the actual
    bootstrap computation to ``stats`` so there is exactly one
    implementation of the resampling logic in the codebase.
    """
    candidate_arr = np.asarray(candidate, dtype=float)
    baseline_arr = np.asarray(baseline, dtype=float)

    if candidate_arr.size == 0 or baseline_arr.size == 0:
        logger.error(
            "Bootstrap CI failed: both distributions must contain observations (candidate size=%d, baseline size=%d).",
            candidate_arr.size,
            baseline_arr.size,
        )
        raise ValueError("Both distributions must contain observations.")

    if n_bootstrap < 1:
        logger.error("Bootstrap CI failed: n_bootstrap must be positive, got %d", n_bootstrap)
        raise ValueError("n_bootstrap must be positive.")

    if not 0.0 < confidence < 1.0:
        logger.error(
            "Bootstrap CI failed: confidence must be between 0 and 1, got %.4f",
            confidence,
        )
        raise ValueError("confidence must be between 0 and 1.")

    logger.debug(
        "Computing bootstrap delta CI: n_bootstrap=%d, confidence=%.2f, candidate_n=%d, baseline_n=%d",
        n_bootstrap,
        confidence,
        candidate_arr.size,
        baseline_arr.size,
    )

    _, ci_low, ci_high = _stats_bootstrap_delta_ci(
        candidate_arr,
        baseline_arr,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence,
        seed=seed,
    )
    ci = (float(ci_low), float(ci_high))
    logger.debug("Bootstrap CI computed: [%.6f, %.6f]", ci[0], ci[1])
    return ci


def select_decision_metric(
    verdicts: list[RegressionVerdict],
) -> RegressionVerdict:
    """Select the primary decision metric based on highest severity and negative effect size.

    Univariate only. Multivariate verdicts have no single ``metric_name``
    and no signed effect size, and the caller's ``scores_by_metric`` lookup
    downstream is keyed on ``metric_name``; feeding a multivariate verdict
    here would raise ``KeyError`` at the lookup, not a clean error. This
    function's contract therefore excludes them by design.
    """
    if not verdicts:
        raise ValueError("At least one verdict is required.")

    selected = min(
        verdicts,
        key=lambda verdict: (
            -SEVERITY_WEIGHT[verdict.severity],
            (verdict.effect_size if verdict.effect_size is not None else 0.0),
        ),
    )
    logger.debug(
        "Selected decision metric '%s' (severity=%s, effect_size=%s)",
        selected.metric_name,
        selected.severity.value,
        selected.effect_size,
    )
    return selected


def evaluate_gate(
    *,
    verdicts: list[RegressionVerdict],
    scores_by_metric: dict[
        str,
        tuple[np.ndarray, np.ndarray],
    ],
    multivariate_verdicts: list[MultivariateVerdict] | None = None,
) -> GateVerdict:
    """Evaluate overall gate verdict across regression metrics.

    ``verdicts`` must contain at least one univariate verdict; the gate is
    fundamentally univariate-anchored, and a caller with only multivariate
    verdicts has not yet run the primary decision track. ``multivariate_verdicts``
    is optional and additive; passing ``None`` or omitting the argument
    reproduces the pre-multivariate-track behavior exactly.

    ``passed`` is ``False`` iff any univariate or multivariate verdict has
    ``severity == BLOCKING``. INCONCLUSIVE multivariate verdicts carry
    ``severity == NONE`` by construction and therefore do not block.
    """
    if not verdicts:
        raise ValueError("Gate requires at least one regression verdict.")

    multivariate_list = list(multivariate_verdicts or [])

    logger.info(
        "Evaluating gate across %d univariate verdict(s) and %d multivariate verdict(s)",
        len(verdicts),
        len(multivariate_list),
    )

    decision_metric = select_decision_metric(verdicts)

    candidate_scores, baseline_scores = scores_by_metric[decision_metric.metric_name]

    confidence_interval = bootstrap_delta_ci(
        candidate_scores,
        baseline_scores,
    )

    univariate_blocking = [
        verdict for verdict in verdicts if verdict.severity == RegressionSeverity.BLOCKING
    ]
    multivariate_blocking = [
        verdict for verdict in multivariate_list if verdict.severity == RegressionSeverity.BLOCKING
    ]
    passed = not univariate_blocking and not multivariate_blocking

    if passed:
        logger.info(
            "Gate evaluation result: PASSED for run_id=%s",
            decision_metric.run_id,
        )
    else:
        logger.warning(
            "Gate evaluation result: BLOCKED for run_id=%s "
            "(%d univariate blocking, %d multivariate blocking)",
            decision_metric.run_id,
            len(univariate_blocking),
            len(multivariate_blocking),
        )

    return GateVerdict(
        passed=passed,
        confidence_interval=confidence_interval,
        regression_verdicts=verdicts,
        multivariate_verdicts=multivariate_list,
        run_id=decision_metric.run_id,
    )
