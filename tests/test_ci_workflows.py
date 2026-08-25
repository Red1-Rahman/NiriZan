# tests/test_ci_workflows.py
"""Regression tests for the CodeQL action pins in the Security (CIA) workflow.

These tests guard the version-comment update made to
`.github/workflows/security.yml`, where the `github/codeql-action/init`
and `github/codeql-action/analyze` steps had their trailing version
comment changed from the bare major version (`# v4`) to the full,
unambiguous semantic version (`# v4.37.7`) that matches the pinned SHA.
"""
import pathlib
import re

import pytest

WORKFLOW_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "security.yml"
)

EXPECTED_SHA = "db488ddef3bf6cb639b32c2e9a7c0a7ea8271d28"
EXPECTED_VERSION_COMMENT = "v4.37.8"
FULL_SEMVER_RE = re.compile(r"^v\d+\.\d+\.\d+$")

# Matches lines such as:
#   - uses: github/codeql-action/init@<40-char-sha> # v4.37.7
CODEQL_ACTION_RE = re.compile(
    r"github/codeql-action/(?P<step>init|analyze)@(?P<sha>[0-9a-f]{40})"
    r"\s*#\s*(?P<comment>\S+)"
)


def _read_workflow_text():
    assert WORKFLOW_PATH.is_file(), f"workflow file not found: {WORKFLOW_PATH}"
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _find_codeql_action_refs(text):
    return {m.group("step"): m for m in CODEQL_ACTION_RE.finditer(text)}


def test_workflow_file_exists():
    assert WORKFLOW_PATH.is_file()


def test_codeql_init_and_analyze_steps_present():
    refs = _find_codeql_action_refs(_read_workflow_text())
    assert "init" in refs, "github/codeql-action/init step not found"
    assert "analyze" in refs, "github/codeql-action/analyze step not found"


def test_codeql_action_pins_use_full_semver_comment():
    refs = _find_codeql_action_refs(_read_workflow_text())
    for step, match in refs.items():
        comment = match.group("comment")
        assert FULL_SEMVER_RE.match(comment), (
            f"{step} action comment '{comment}' should be a full semantic "
            f"version (e.g. 'v4.37.7'), not a bare major version like 'v4'"
        )
        assert comment == EXPECTED_VERSION_COMMENT, (
            f"{step} action comment '{comment}' does not match expected "
            f"'{EXPECTED_VERSION_COMMENT}'"
        )


def test_codeql_init_and_analyze_share_same_pinned_sha():
    refs = _find_codeql_action_refs(_read_workflow_text())
    assert refs["init"].group("sha") == EXPECTED_SHA
    assert refs["analyze"].group("sha") == EXPECTED_SHA
    assert refs["init"].group("sha") == refs["analyze"].group("sha")


def test_codeql_action_comment_does_not_regress_to_bare_major_version():
    text = _read_workflow_text()
    # Regression guard: these lines previously used a bare "# v4" comment,
    # which is ambiguous since the SHA it points to is tagged v4.37.7.
    bare_version_pattern = re.compile(
        r"github/codeql-action/(?:init|analyze)@[0-9a-f]{40}\s*#\s*v4\s*$",
        re.MULTILINE,
    )
    assert not bare_version_pattern.search(text), (
        "codeql-action references regressed to a bare '# v4' version comment"
    )


def test_codeql_init_step_config_unchanged():
    # The init step's `with:` block (languages/queries) must remain intact
    # after the version-comment update.
    lines = _read_workflow_text().splitlines()
    init_idx = next(
        i for i, line in enumerate(lines) if "github/codeql-action/init@" in line
    )
    following = "\n".join(lines[init_idx + 1 : init_idx + 4])
    assert "with:" in following
    assert "languages: python" in following
    assert "queries: +security-and-quality" in following


def test_workflow_yaml_is_parseable():
    yaml = pytest.importorskip("yaml")
    parsed = yaml.safe_load(_read_workflow_text())
    codeql_job = parsed["jobs"]["codeql"]
    uses_values = [s["uses"] for s in codeql_job["steps"] if "uses" in s]
    assert any(u.startswith("github/codeql-action/init@") for u in uses_values)
    assert any(u.startswith("github/codeql-action/analyze@") for u in uses_values)
