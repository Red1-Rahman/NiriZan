"""Regression detection layer.

Compares active run metrics against historical baselines using statistical checks
(e.g., Z-scores) to assign severity levels to regressions.
"""
from nirizan.regression.comparator import (
    BaselineComparator,
    RegressionSeverity,
    RegressionVerdict,
    classify_severity,
    cohens_d,
    mean_delta,
)

__all__ = [
    "BaselineComparator",
    "RegressionSeverity",
    "RegressionVerdict",
    "classify_severity",
    "cohens_d",
    "mean_delta",
]
