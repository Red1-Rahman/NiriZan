# tests\test_documentation.py
"""Regression checks for release and bootstrap-shim documentation."""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_current_release_version_is_consistent_in_release_docs() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    user_manual = (ROOT / "docs" / "user-manual.md").read_text(encoding="utf-8")

    assert 'version = "0.4.0"' in pyproject
    assert "## [0.4.0]" in changelog
    assert "> version: `0.4.0`" in user_manual


def test_bootstrap_documentation_distinguishes_canonical_api_and_gate_shim() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    gate_verdict = (ROOT / "src" / "nirizan" / "gate" / "verdict.py").read_text(encoding="utf-8")

    assert "canonical `nirizan.metrics.stats.bootstrap_delta_ci`" in changelog
    assert "2-tuple wrapper" in changelog
    assert "deprecated 2-tuple shim" in gate_verdict
    assert "from nirizan.metrics.statistical_gating import bootstrap_delta_ci" in changelog
