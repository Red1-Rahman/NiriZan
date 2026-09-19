# src\nirizan\metrics\stats.py
"""Centralized statistical utilities for NiriZan metrics, regression, and gates.

This module is the single source of truth for the statistical primitives
shared across NiriZan. Specifics:

* ``bootstrap_delta_ci`` returns the 3-tuple ``(delta_hat, ci_lower, ci_upper)``.
  The 2-tuple wrappers in ``metrics/statistical_gating.py`` and
  ``gate/verdict.py`` are deprecated; both should call this function and
  discard ``delta_hat`` if they only need the interval.
* ``cohens_d`` lives here, not in ``regression/comparator.py``. The
  comparator imports it from here for backward compatibility.
* The multivariate structure track's statistics (``scale_logvar_test``,
  ``dependence_max_t_test``) also live here, alongside the shared
  ``permutation_test`` engine, so that observed and permutation statistics
  share a single code path.

Project conventions that apply to this module:
* No pydantic models here, so ``ConfigDict(strict=True)`` does not appear.
  Where this module's outputs are consumed by models, the models carry
  that config themselves.
* No datetime values here. Where this module's outputs feed records that
  timestamp results, those records use timezone-aware UTC datetimes via
  the ``datetime.UTC`` alias (Python 3.11+), never ``datetime.now()``
  without a tz, never ``utcnow()``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal, cast

import numpy as np
from scipy.stats import mannwhitneyu, norm, rankdata

from nirizan._logging import get_logger

logger = get_logger(__name__)


def validate_scores(scores: np.ndarray | Sequence[float]) -> np.ndarray:
    """Validate metric score arrays for finite values and bounded range [0, 1]."""
    arr = np.asarray(scores, dtype=float)
    if arr.ndim != 1:
        raise ValueError("Scores must be one-dimensional.")
    if arr.size == 0:
        raise ValueError("Score distribution is empty.")
    if not np.isfinite(arr).all():
        raise ValueError("Scores contain non-finite values (NaN/Inf).")
    if np.any(arr < 0.0) or np.any(arr > 1.0):
        raise ValueError("NiriZan metric scores must be normalized to [0, 1].")
    logger.debug("Successfully validated %d score observations", arr.size)
    return arr


def validate_score_matrix(
    scores: np.ndarray | Sequence[Sequence[float]],
    *,
    min_rows: int = 2,
    min_columns: int = 1,
) -> np.ndarray:
    """Validate a 2-D metric-score matrix.

    Each row is one trace's scores across all metrics; each column is one
    metric. Every entry must be finite and in ``[0, 1]``. Rows with any
    non-finite entry should be dropped by the caller (via ``ScoreMatrix``
    construction), not silently coerced here.
    """
    arr = np.asarray(scores, dtype=float)
    if arr.ndim != 2:
        raise ValueError("Score matrix must be two-dimensional.")
    if arr.shape[0] < min_rows:
        raise ValueError(f"Score matrix has {arr.shape[0]} rows; at least {min_rows} required.")
    if arr.shape[1] < min_columns:
        raise ValueError(
            f"Score matrix has {arr.shape[1]} columns; at least {min_columns} required."
        )
    if not np.isfinite(arr).all():
        raise ValueError("Score matrix contains non-finite values (NaN/Inf).")
    if np.any(arr < 0.0) or np.any(arr > 1.0):
        raise ValueError("NiriZan metric scores must be normalized to [0, 1].")
    return arr


def _as_validated_pair(
    x: np.ndarray | Sequence[float] | Sequence[Sequence[float]],
    y: np.ndarray | Sequence[float] | Sequence[Sequence[float]],
    *,
    min_metrics: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """Coerce and validate ``x`` / ``y`` as a 2-D ``(n, p)`` pair.

    A 1-D input is treated as a single-metric sample and reshaped to
    ``(n, 1)``. Both arrays must end up 2-D with the same ``p``.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    if x_arr.ndim == 1:
        x_arr = x_arr[:, None]
    if y_arr.ndim == 1:
        y_arr = y_arr[:, None]
    if x_arr.ndim != 2 or y_arr.ndim != 2:
        raise ValueError("x and y must be 1-D or 2-D arrays.")
    if x_arr.shape[1] != y_arr.shape[1]:
        raise ValueError("x and y must have the same number of columns.")
    if x_arr.shape[1] < min_metrics:
        raise ValueError(f"Requires at least {min_metrics} metric(s), got {x_arr.shape[1]}.")
    for name, arr in (("x", x_arr), ("y", y_arr)):
        if arr.shape[0] < 2:
            raise ValueError(f"{name} must have at least 2 observations.")
        if not np.isfinite(arr).all():
            raise ValueError(f"{name} contains non-finite values (NaN/Inf).")
        if np.any(arr < 0.0) or np.any(arr > 1.0):
            raise ValueError(f"{name} contains scores outside the [0, 1] range.")
    return x_arr, y_arr


def cohens_d(
    candidate_scores: np.ndarray | Sequence[float],
    baseline_scores: np.ndarray | Sequence[float],
) -> float:
    """Cohen's d effect size between candidate and baseline.

    Uses the pooled standard deviation formula
    ``sqrt((s_c² + s_b²) / 2)`` rather than the equal-n pooled formula,
    since candidate and baseline sizes routinely differ in production.
    Returns ``0.0`` when the pooled standard deviation is exactly zero
    (both distributions constant) rather than raising or returning inf;
    a zero-variance pair has no meaningful effect size.
    """
    cand = validate_scores(candidate_scores)
    base = validate_scores(baseline_scores)
    candidate_std = float(cand.std(ddof=1))
    baseline_std = float(base.std(ddof=1))
    pooled_std = math.sqrt((candidate_std**2 + baseline_std**2) / 2.0)
    if pooled_std == 0.0:
        return 0.0
    return float((cand.mean() - base.mean()) / pooled_std)


def bootstrap_delta_ci(
    candidate_scores: np.ndarray | Sequence[float],
    baseline_scores: np.ndarray | Sequence[float],
    *,
    confidence_level: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int | None = None,
) -> tuple[float, float, float]:
    """Compute bootstrap confidence interval for the mean delta (candidate - baseline)."""
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be positive.")
    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be strictly between 0 and 1.")

    cand = validate_scores(candidate_scores)
    base = validate_scores(baseline_scores)

    delta_hat = float(np.mean(cand) - np.mean(base))

    rng = np.random.default_rng(seed)
    cand_boot = rng.choice(cand, size=(n_bootstrap, len(cand)), replace=True)
    base_boot = rng.choice(base, size=(n_bootstrap, len(base)), replace=True)

    boot_deltas = np.mean(cand_boot, axis=1) - np.mean(base_boot, axis=1)

    alpha = 1.0 - confidence_level
    ci_lower = float(np.percentile(boot_deltas, (alpha / 2.0) * 100.0))
    ci_upper = float(np.percentile(boot_deltas, (1.0 - alpha / 2.0) * 100.0))

    return delta_hat, ci_lower, ci_upper


def mann_whitney_regression(
    candidate_scores: np.ndarray | Sequence[float],
    baseline_scores: np.ndarray | Sequence[float],
    *,
    alternative: Literal["less", "greater", "two-sided"] = "less",
) -> tuple[float, float]:
    """Perform Mann-Whitney U test to evaluate score regression between candidate and baseline.

    Returns ``(statistic, p_value)``. scipy's type stubs for
    ``mannwhitneyu`` declare the result as a generic tuple whose element
    type is ``_T_co@tuple``, so neither attribute access nor positional
    unpacking resolves to a concrete ``float`` for a static checker. We
    cast the whole result to ``Any`` at this single point and read the
    named-tuple fields off it. The runtime object is a
    ``MannwhitneyuResult`` with both fields, so behavior is unchanged;
    the cast is the documented escape hatch for the stub gap, contained
    to one expression.
    """
    cand = validate_scores(candidate_scores)
    base = validate_scores(baseline_scores)
    if len(cand) < 5 or len(base) < 5:
        raise ValueError("at least five observations are required in each group.")

    result = mannwhitneyu(cand, base, alternative=alternative)
    result_any = cast(Any, result)
    return float(result_any.statistic), float(result_any.pvalue)


def holm_bonferroni(
    p_values: Mapping[str, float],
    *,
    alpha: float = 0.05,
) -> dict[str, bool]:
    """Apply Holm-Bonferroni step-down correction for multiple hypothesis testing."""
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be strictly between 0 and 1.")

    if not p_values:
        return {}

    sorted_items = sorted(p_values.items(), key=lambda item: item[1])
    m = len(sorted_items)

    rejected: dict[str, bool] = dict.fromkeys(p_values.keys(), False)

    stopped = False
    for k, (key, p_val) in enumerate(sorted_items, start=1):
        if stopped:
            rejected[key] = False
            continue

        threshold = alpha / (m - k + 1)
        if p_val <= threshold:
            rejected[key] = True
        else:
            stopped = True

    return rejected


def calculate_sample_size(
    *,
    baseline_std: float,
    target_delta: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Calculate the approximate per-group sample size for a two-sided target delta."""
    if baseline_std <= 0:
        raise ValueError("baseline_std must be positive.")
    if target_delta <= 0:
        raise ValueError("target_delta must be positive.")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be between 0 and 1.")
    if not (0.0 < power < 1.0):
        raise ValueError("power must be between 0 and 1.")

    z_alpha = norm.ppf(1.0 - alpha / 2.0)
    z_beta = norm.ppf(power)
    n = 2.0 * ((z_alpha + z_beta) * baseline_std / target_delta) ** 2
    return int(np.ceil(n))


def compute_calibration_metrics(
    predictions: np.ndarray | Sequence[float],
    gold_labels: np.ndarray | Sequence[float],
) -> dict[str, float]:
    """Calculate calibration error metrics (MAE, MSE, RMSE) against gold labels."""
    preds = np.asarray(predictions, dtype=float)
    labels = np.asarray(gold_labels, dtype=float)
    if preds.shape != labels.shape:
        raise ValueError("predictions and gold_labels must have the same shape.")

    mae = float(np.mean(np.abs(preds - labels)))
    mse = float(np.mean((preds - labels) ** 2))
    rmse = float(np.sqrt(mse))
    return {"mae": mae, "mse": mse, "rmse": rmse}


# ---------------------------------------------------------------------------
# Permutation tests: shared engine, p-value convention, and the two
# multivariate structure statistics (variance-only and dependence-only).
# ---------------------------------------------------------------------------


def permutation_p_value(
    observed: float,
    null: np.ndarray,
    *,
    alternative: Literal["greater", "less", "two-sided"] = "greater",
) -> float:
    """Exact permutation p-value with the ``(k + 1) / (R + 1)`` correction.

    The ``+1`` in the numerator is the observed value itself (treated as
    one more permutation, the identity one); the ``+1`` in the denominator
    accounts for it. This matches the convention used by the notebook's
    existing permutation-calibrated tests (welch_t2, energy, mmd, etc.)
    and guarantees ``p > 0`` even when the observed statistic is extreme.
    """
    null_arr = np.asarray(null, dtype=float)
    if null_arr.ndim != 1 or null_arr.size == 0:
        raise ValueError("null must be a non-empty 1-D array.")
    if alternative == "greater":
        count = int((null_arr >= observed).sum())
    elif alternative == "less":
        count = int((null_arr <= observed).sum())
    elif alternative == "two-sided":
        count = int((np.abs(null_arr) >= abs(observed)).sum())
    else:
        raise ValueError(f"Unknown alternative: {alternative}")
    return (count + 1) / (null_arr.size + 1)


def permutation_test(
    x: np.ndarray | Sequence[float],
    y: np.ndarray | Sequence[float],
    statistic_fn: Callable[[np.ndarray, np.ndarray], float],
    *,
    n_permutations: int = 999,
    seed: int | None = None,
) -> tuple[float, np.ndarray]:
    """Generic two-sample permutation test.

    The pooled data is sliced into ``n_permutations`` random splits and
    ``statistic_fn`` is evaluated on each. The observed value is computed
    on the actual ``x`` / ``y`` split using the same ``statistic_fn``, so
    observed and null share a code path — this is the invariant the
    notebook's ablation was careful to preserve, and the reason a bug in
    one branch cannot silently corrupt every p-value.

    Parameters
    ----------
    x, y : array-like
        Baseline and candidate samples. Rows are observations, columns are
        metrics. A 1-D input is treated as a single-metric sample.
    statistic_fn : callable
        ``(x_arr, y_arr) -> float``. Must accept 2-D arrays.
    n_permutations : int
        Number of permutations. The observed value is not counted.
    seed : int or None
        RNG seed. ``None`` uses system entropy.

    Returns
    -------
    observed : float
        Statistic on the actual ``x`` / ``y`` split.
    null : np.ndarray, shape ``(n_permutations,)``
        Statistic values from random pooled splits.
    """
    x_arr, y_arr = _as_validated_pair(x, y)
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive.")

    return _permutation_distribution(
        x_arr,
        y_arr,
        statistic_fn,
        n_permutations=n_permutations,
        seed=seed,
    )


def _permutation_distribution(
    x: np.ndarray,
    y: np.ndarray,
    statistic_fn: Callable[[np.ndarray, np.ndarray], float],
    *,
    n_permutations: int,
    seed: int | None,
) -> tuple[float, np.ndarray]:
    """Evaluate a statistic and its random-label permutation distribution.

    Unlike :func:`permutation_test`, this internal helper assumes its inputs
    have already been validated or transformed by a caller. This permits the
    structure tests to remove nuisance parameters before pooling while keeping
    their observed and permuted statistics on one implementation path.
    """
    z = np.vstack([x, y])
    n1 = x.shape[0]
    rng = np.random.default_rng(seed)

    observed = float(statistic_fn(x, y))
    null = np.empty(n_permutations, dtype=float)
    for k in range(n_permutations):
        idx = rng.permutation(z.shape[0])
        null[k] = float(statistic_fn(z[idx[:n1]], z[idx[n1:]]))
    return observed, null


# --- Variance-only statistic -------------------------------------------------


def scale_logvar_statistic(
    x: np.ndarray | Sequence[float],
    y: np.ndarray | Sequence[float],
    *,
    eps: float = 1e-12,
) -> float:
    """Variance-only statistic: ``Σ_j (log s²_{y,j} - log s²_{x,j})²``.

    ``eps`` floors the variances before the log, guarding against
    zero-variance columns (metric scores routinely saturate against the
    ``[0, 1]`` boundaries). The statistic is undirected: a variance
    increase and a decrease of equal magnitude produce the same value.

    Rows are observations, columns are metrics. A 1-D input is treated as
    a single-metric sample.
    """
    if not math.isfinite(eps) or eps <= 0.0:
        raise ValueError("eps must be finite and positive.")
    x_arr, y_arr = _as_validated_pair(x, y)
    return _scale_logvar_from_arrays(x_arr, y_arr, eps=eps)


def _scale_logvar_from_arrays(x: np.ndarray, y: np.ndarray, *, eps: float) -> float:
    """Compute the scale statistic from prevalidated arrays.

    This is shared by the public statistic and the centred-residual
    permutation null. Centering may yield negative residuals, so validating
    the score range again here would incorrectly reject that valid null.
    """
    vx = x.var(axis=0, ddof=1)
    vy = y.var(axis=0, ddof=1)
    log_diff = np.log(vx + eps) - np.log(vy + eps)
    return float((log_diff**2).sum())


def scale_logvar_test(
    x: np.ndarray | Sequence[float],
    y: np.ndarray | Sequence[float],
    *,
    n_permutations: int = 999,
    seed: int | None = None,
    eps: float = 1e-12,
) -> tuple[float, np.ndarray, float]:
    """Permutation-calibrated variance-only test.

    Returns ``(observed, null, p_value)``. The permutation null removes
    nuisance location. Each group's column means are removed before
    pooling residuals and permuting labels; raw values are not exchangeable
    under a pure location shift. Variance is translation-invariant, so this
    leaves the observed statistic unchanged for the intended location-shift
    family with identically distributed residuals and a common scale.
    """
    if not math.isfinite(eps) or eps <= 0.0:
        raise ValueError("eps must be finite and positive.")
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive.")
    x_arr, y_arr = _as_validated_pair(x, y)
    centered_x = x_arr - x_arr.mean(axis=0, keepdims=True)
    centered_y = y_arr - y_arr.mean(axis=0, keepdims=True)
    observed, null = _permutation_distribution(
        centered_x,
        centered_y,
        lambda xa, ya: _scale_logvar_from_arrays(xa, ya, eps=eps),
        n_permutations=n_permutations,
        seed=seed,
    )
    p_value = permutation_p_value(observed, null, alternative="greater")
    return observed, null, p_value


# --- Dependence-only statistic ----------------------------------------------


def _rank_columns(z: np.ndarray) -> np.ndarray:
    """Rank each column of ``z`` independently (average ties).

    Applied separately to each group (``x`` and ``y``, or each permuted
    split), never to the pooled data. Spearman/rank correlation is
    invariant to a monotonic transform of a variable *within its own
    group* — ranking a group jointly with another group and then slicing
    the joint ranks back apart does **not** preserve that invariance,
    because a value's rank then depends on where the other group's values
    happen to interleave with it. Rank-within-group is what makes the
    dependence statistic blind to a pure per-column rescale of one group
    relative to the other, which is the whole point of using rank
    correlation instead of covariance Frobenius (see the module docstring
    and ``dependence_max_t_statistic``).
    """
    ranked = np.empty_like(z, dtype=float)
    for j in range(z.shape[1]):
        ranked[:, j] = rankdata(z[:, j])
    return ranked


def _pearson_from_ranks(r: np.ndarray) -> np.ndarray:
    """Pearson correlation matrix from a rank matrix. Equivalent to Spearman.

    Columns with zero variance within the group contribute zero correlation
    rather than NaN; under the permutation null this asymmetry is symmetric
    across the two groups, so it does not bias the test.
    """
    centered = r - r.mean(axis=0, keepdims=True)
    norms = np.sqrt((centered**2).sum(axis=0))
    norms = np.where(norms == 0.0, 1.0, norms)
    normalized = centered / norms
    corr: np.ndarray = np.asarray(normalized.T @ normalized)
    corr = (corr + corr.T) / 2.0
    np.clip(corr, -1.0, 1.0, out=corr)
    return corr


def _dependence_max_t_from_groups(x_arr: np.ndarray, y_arr: np.ndarray) -> float:
    """max |Δρ| over off-diagonal pairs, ranking ``x`` and ``y`` independently.

    Each group is ranked **within itself** (see ``_rank_columns``), not as
    a pooled-then-split ranking. This is what gives the statistic its
    ablation-critical invariance property: a per-column positive affine
    rescale of one group relative to the other leaves each group's own
    internal rank order, and therefore its Spearman correlation matrix,
    completely unchanged, so the statistic is exactly zero.
    """
    rx = _rank_columns(x_arr)
    ry = _rank_columns(y_arr)
    cx = _pearson_from_ranks(rx)
    cy = _pearson_from_ranks(ry)
    p = cx.shape[0]
    iu = np.triu_indices(p, k=1)
    return float(np.abs(cx[iu] - cy[iu]).max())


def dependence_max_t_statistic(
    x: np.ndarray | Sequence[float],
    y: np.ndarray | Sequence[float],
) -> float:
    """Dependence-structure statistic: ``max |Δρ|`` over off-diagonal pairs.

    Uses **rank** correlation (Spearman), not covariance Frobenius. The
    ablation showed that covariance Frobenius leaks variance changes into
    the dependence test (17.9% firing on variance-only vs 4.5% for the
    rank version), because the covariance matrix conflates scale and
    dependence. Rank correlation isolates dependence from marginals, which
    is what the structure track is supposed to detect.

    Each of ``x`` and ``y`` is ranked **independently, within its own
    group** (not pooled), which is what makes the statistic exactly
    invariant to a per-column positive affine rescale of one group
    relative to the other — a pure variance-only change that leaves every
    marginal's rank order untouched must not move this statistic.

    Rows are observations, columns are metrics. Requires ``p >= 2``; a
    single metric has no pairwise dependence to test.
    """
    x_arr, y_arr = _as_validated_pair(x, y, min_metrics=2)
    return _dependence_max_t_from_groups(x_arr, y_arr)


def dependence_max_t_test(
    x: np.ndarray | Sequence[float],
    y: np.ndarray | Sequence[float],
    *,
    n_permutations: int = 999,
    seed: int | None = None,
) -> tuple[float, np.ndarray, float]:
    """Permutation-calibrated rank-dependence test.

    The null hypothesis is equal dependence (copula), not equal marginal
    location or scale. Raw rows are consequently not exchangeable when a
    group has a different marginal transformation. Each group is first
    converted to columnwise rank pseudo-observations, then those row vectors
    are pooled and relabelled. The statistic re-ranks every split, preserving
    its tie handling and keeping observed and null calculations aligned.

    Returns ``(observed, null, p_value)`` with the same ``(k + 1) / (R + 1)``
    convention as the other permutation tests.
    """
    x_arr, y_arr = _as_validated_pair(x, y, min_metrics=2)
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive.")

    x_pseudo = _rank_columns(x_arr) / (x_arr.shape[0] + 1.0)
    y_pseudo = _rank_columns(y_arr) / (y_arr.shape[0] + 1.0)
    observed, null = _permutation_distribution(
        x_pseudo,
        y_pseudo,
        _dependence_max_t_from_groups,
        n_permutations=n_permutations,
        seed=seed,
    )

    p_value = permutation_p_value(observed, null, alternative="greater")
    return observed, null, p_value


# Aliases for backward compatibility
calculate_bootstrap_ci = bootstrap_delta_ci
compute_holm_bonferroni = holm_bonferroni
compute_mann_whitney_u = mann_whitney_regression

__all__ = [
    "bootstrap_delta_ci",
    "calculate_bootstrap_ci",
    "calculate_sample_size",
    "cohens_d",
    "compute_calibration_metrics",
    "compute_holm_bonferroni",
    "compute_mann_whitney_u",
    "dependence_max_t_statistic",
    "dependence_max_t_test",
    "holm_bonferroni",
    "mann_whitney_regression",
    "permutation_p_value",
    "permutation_test",
    "scale_logvar_statistic",
    "scale_logvar_test",
    "validate_score_matrix",
    "validate_scores",
]
