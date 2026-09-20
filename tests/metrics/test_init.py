# tests/metrics/test_init.py
"""Tests for the public surface of :mod:`nirizan.metrics`.

This module tests ``src/nirizan/metrics/__init__.py`` specifically: the
names it re-exports and the shape of the ``bootstrap_delta_ci`` it exposes
at package level. Tests of individual submodules live in their own files
(``test_stats.py``, ``test_statistical_gating.py``, etc.).

The package surface is a real contract: downstream code imports
``from nirizan.metrics import ...``, and the meaning of that import is
different from ``from nirizan.metrics.statistical_gating import ...``
after the stats consolidation. These tests pin the difference.
"""

from __future__ import annotations

import numpy as np

import nirizan.metrics as metrics
from nirizan.metrics.statistical_gating import (
    bootstrap_delta_ci as shim_bootstrap_delta_ci,
)
from nirizan.metrics.stats import bootstrap_delta_ci as canonical_bootstrap_delta_ci


def test_package_level_bootstrap_delta_ci_is_canonical_3_tuple() -> None:
    """The package-level ``bootstrap_delta_ci`` must be the canonical
    3-tuple version from ``stats``, not the deprecated 2-tuple shim from
    ``statistical_gating``.

    Uses ``is`` rather than ``==`` so the test fails if a future change
    reintroduces an independent implementation (or a same-behavior-but-
    different-object wrapper) instead of re-exporting the canonical one.
    """
    assert metrics.bootstrap_delta_ci is canonical_bootstrap_delta_ci
    assert metrics.bootstrap_delta_ci is not shim_bootstrap_delta_ci

    candidate = np.array([0.4, 0.5, 0.6, 0.5, 0.4])
    baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
    result = metrics.bootstrap_delta_ci(candidate, baseline, n_bootstrap=200, seed=1)
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_package_level_exports_include_new_stats_names() -> None:
    """Every new statistics primitive added to ``stats.py`` must also be
    re-exported from the package, since the documented surface of
    ``nirizan.metrics`` is the aggregation point downstream callers use.
    """
    expected = {
        "cohens_d",
        "dependence_max_t_statistic",
        "dependence_max_t_test",
        "permutation_p_value",
        "permutation_test",
        "scale_logvar_statistic",
        "scale_logvar_test",
        "validate_score_matrix",
    }
    missing = expected - set(metrics.__all__)
    assert not missing, f"Missing from metrics.__all__: {sorted(missing)}"
    for name in expected:
        assert hasattr(metrics, name), f"metrics.{name} is not importable"
