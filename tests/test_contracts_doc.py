# tests/test_contracts_doc.py
"""Regression tests for `docs/contracts.md`.

`docs/contracts.md` is documentation, not importable code, so these tests
guard the two things that can silently break about a contracts document:

1. Structural/formatting invariants introduced by this revision: fenced
   code blocks stay balanced, the previously-stray four-backtick fence and
   plain (unlabeled) fence for the import-direction diagram do not
   regress, "Contract guarantees:" bullet lists consistently use `*`
   markers (this revision normalized them from `-`), and every embedded
   Python snippet remains syntactically valid.

2. That the two newly-documented Phase 5 reporting contracts,
   `JudgeReliabilityStatus`/`JudgeReliabilityMetrics`
   (`reporting/judge_reliability.py`) and `DashboardSnapshot`
   (`reporting/dashboard.py`), accurately describe the real
   implementation: same field names, same enum members, same default
   warning threshold. A docs PR that adds a contract description is only
   useful if it doesn't drift from the code it describes.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from nirizan.reporting.dashboard import DashboardSnapshot
from nirizan.reporting.judge_reliability import (
    DEFAULT_JUDGE_DRIFT_RATE_WARNING,
    JudgeReliabilityMetrics,
    JudgeReliabilityStatus,
)

CONTRACTS_PATH = Path(__file__).resolve().parents[1] / "docs" / "contracts.md"

_PYTHON_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)
_CONTRACT_GUARANTEES_RE = re.compile(r"\*\*Contract guarantees:\*\*")


def _read_contracts_text() -> str:
    assert CONTRACTS_PATH.is_file(), f"contracts doc not found: {CONTRACTS_PATH}"
    return CONTRACTS_PATH.read_text(encoding="utf-8")


def _python_code_blocks(text: str) -> list[str]:
    return _PYTHON_FENCE_RE.findall(text)


def _extract_class_def(block: str, class_name: str) -> ast.ClassDef | None:
    """Return the `ast.ClassDef` node for `class_name` within a code block, if present."""
    tree = ast.parse(block)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _annotated_field_names(class_def: ast.ClassDef) -> list[str]:
    """Field names declared as `name: type` (or with a default) inside a class body.

    Excludes `model_config`, which is pydantic configuration, not a data field.
    """
    names = []
    for stmt in class_def.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id != "model_config":
                names.append(stmt.target.id)
    return names


@pytest.fixture(scope="module")
def contracts_text() -> str:
    return _read_contracts_text()


class TestContractsDocStructure:
    """Formatting/structural invariants for the document as a whole."""

    def test_file_exists(self):
        assert CONTRACTS_PATH.is_file()

    def test_fenced_code_blocks_are_balanced(self, contracts_text):
        fence_lines = re.findall(r"^```", contracts_text, re.MULTILINE)
        assert len(fence_lines) % 2 == 0, "unbalanced ``` fences in contracts.md"

    def test_no_stray_quadruple_backtick_fences(self, contracts_text):
        # The BaselineRepository section previously used a stray ```` fence
        # (four backticks); this revision normalized it to a standard
        # triple-backtick fence. Guard against it coming back.
        assert "````" not in contracts_text

    def test_python_code_blocks_are_syntactically_valid(self, contracts_text):
        blocks = _python_code_blocks(contracts_text)
        assert len(blocks) >= 20, "expected many python code blocks in contracts.md"
        for block in blocks:
            # Each snippet is meant to be readable in isolation; even
            # Protocol bodies using `...` and forward references like
            # "RunDiff" are valid standalone syntax without needing the
            # imports/types assumed from earlier in the document.
            ast.parse(block)

    def test_import_direction_diagram_uses_labeled_text_fence(self, contracts_text):
        # The import-direction ASCII diagram previously used a bare ``` fence;
        # this revision labels it ```text so renderers don't try to syntax-
        # highlight it as a language.
        assert "```text\ninstrumentation" in contracts_text

    def test_contract_guarantees_bullets_use_asterisk_marker(self, contracts_text):
        headers = list(_CONTRACT_GUARANTEES_RE.finditer(contracts_text))
        assert len(headers) >= 20, "expected many '**Contract guarantees:**' sections"
        for match in headers:
            following = contracts_text[match.end() : match.end() + 3]
            assert following.startswith("\n\n*"), (
                "'**Contract guarantees:**' must be followed by a blank line "
                f"and a '*' bullet, got {following!r}"
            )

    def test_no_dash_bullet_markers_remain(self, contracts_text):
        # This revision normalized every "- " bullet in the document to "* ".
        # A stray "- " bullet line would indicate a regression to the old,
        # inconsistent style.
        dash_bullets = re.findall(r"^\s*-\s", contracts_text, re.MULTILINE)
        assert not dash_bullets, f"found regressed '-' bullet markers: {dash_bullets}"


class TestJudgeReliabilityContractMatchesImplementation:
    """Cross-check the newly-added JudgeReliabilityStatus/Metrics docs."""

    def _status_block(self, contracts_text: str) -> str:
        blocks = _python_code_blocks(contracts_text)
        for block in blocks:
            if "class JudgeReliabilityStatus" in block:
                return block
        pytest.fail("JudgeReliabilityStatus code block not found in contracts.md")

    def _metrics_block(self, contracts_text: str) -> str:
        blocks = _python_code_blocks(contracts_text)
        for block in blocks:
            if "class JudgeReliabilityMetrics" in block:
                return block
        pytest.fail("JudgeReliabilityMetrics code block not found in contracts.md")

    def test_status_enum_members_match_implementation(self, contracts_text):
        block = self._status_block(contracts_text)
        class_def = _extract_class_def(block, "JudgeReliabilityStatus")
        assert class_def is not None

        documented_members = {}
        for stmt in class_def.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        documented_members[target.id] = ast.literal_eval(stmt.value)

        real_members = {m.name: m.value for m in JudgeReliabilityStatus}
        assert documented_members == real_members

    def test_metrics_field_names_match_implementation(self, contracts_text):
        block = self._metrics_block(contracts_text)
        class_def = _extract_class_def(block, "JudgeReliabilityMetrics")
        assert class_def is not None

        documented_fields = _annotated_field_names(class_def)
        real_fields = list(JudgeReliabilityMetrics.model_fields.keys())
        assert documented_fields == real_fields

    def test_default_drift_rate_warning_matches_documented_value(self, contracts_text):
        # The doc states: "The current default warning threshold is 0.10."
        assert "current default warning threshold is `0.10`" in contracts_text
        assert DEFAULT_JUDGE_DRIFT_RATE_WARNING == pytest.approx(0.10)


class TestDashboardSnapshotContractMatchesImplementation:
    """Cross-check the newly-added DashboardSnapshot docs."""

    def _snapshot_block(self, contracts_text: str) -> str:
        blocks = _python_code_blocks(contracts_text)
        for block in blocks:
            if "class DashboardSnapshot" in block:
                return block
        pytest.fail("DashboardSnapshot code block not found in contracts.md")

    def test_snapshot_field_names_match_implementation(self, contracts_text):
        block = self._snapshot_block(contracts_text)
        class_def = _extract_class_def(block, "DashboardSnapshot")
        assert class_def is not None

        documented_fields = _annotated_field_names(class_def)
        real_fields = list(DashboardSnapshot.model_fields.keys())
        assert documented_fields == real_fields

    def test_health_score_bounds_documented_match_field_constraints(self, contracts_text):
        block = self._snapshot_block(contracts_text)
        assert "health_score: float = Field(ge=0.0, le=100.0)" in block

        health_score_field = DashboardSnapshot.model_fields["health_score"]
        # Ge/Le constraints on the real model must match what's documented.
        ge_values = [c.ge for c in health_score_field.metadata if hasattr(c, "ge")]
        le_values = [c.le for c in health_score_field.metadata if hasattr(c, "le")]
        assert 0.0 in ge_values
        assert 100.0 in le_values


class TestPhase5SectionOrdering:
    """The new sections must be documented in the right place within Phase 5."""

    def test_new_sections_appear_between_anchor_set_and_behavioral_anchor_metric(
        self, contracts_text
    ):
        anchor_set_idx = contracts_text.index("### `AnchorSet` (`trust/anchor_set.py`)")
        status_idx = contracts_text.index(
            "### `JudgeReliabilityStatus` (`reporting/judge_reliability.py`)"
        )
        metrics_idx = contracts_text.index(
            "### `JudgeReliabilityMetrics` (`reporting/judge_reliability.py`)"
        )
        snapshot_idx = contracts_text.index(
            "### `DashboardSnapshot` (`reporting/dashboard.py`)"
        )
        behavioral_idx = contracts_text.index("### `BehavioralAnchorMetric`")

        assert (
            anchor_set_idx
            < status_idx
            < metrics_idx
            < snapshot_idx
            < behavioral_idx
        )

    def test_new_sections_are_within_phase_5(self, contracts_text):
        phase5_idx = contracts_text.index(
            "## Phase 5 Contracts: Drift & Judge-Reliability Layer"
        )
        import_direction_idx = contracts_text.index(
            "## Import Direction Rule (applies to every phase)"
        )
        status_idx = contracts_text.index(
            "### `JudgeReliabilityStatus` (`reporting/judge_reliability.py`)"
        )
        snapshot_idx = contracts_text.index(
            "### `DashboardSnapshot` (`reporting/dashboard.py`)"
        )
        assert phase5_idx < status_idx < snapshot_idx < import_direction_idx