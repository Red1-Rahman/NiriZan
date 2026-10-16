# tests\test_documentation.py
"""Regression checks for release and bootstrap-shim documentation."""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]

# Modules whose ``__all__`` is a public contract that contracts.md and
# architecture.md must document. Parsed from source (never imported) so this
# core-only test never pulls in the optional ``opentelemetry`` packages.
OTEL_BRIDGE_MODULES = [
    "instrumentation/otel/__init__.py",
    "instrumentation/otel/_id_mapping.py",
    "instrumentation/otel/from_otel.py",
    "instrumentation/otel/to_otel.py",
    "instrumentation/otel/semconv.py",
]


def public_names(relative_module: str) -> list[str]:
    """The ``__all__`` of a source file, read via AST instead of import."""
    source = (ROOT / "src" / "nirizan" / relative_module).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            assert isinstance(node.value, ast.List), f"{relative_module} __all__ must be a list"
            names: list[str] = []
            for element in node.value.elts:
                assert isinstance(element, ast.Constant), (
                    f"{relative_module} __all__ must contain only string literals"
                )
                assert isinstance(element.value, str)
                names.append(element.value)
            return names
    raise AssertionError(f"{relative_module} does not define __all__")


def test_current_release_version_is_consistent_in_release_docs() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    user_manual = (ROOT / "docs" / "user-manual.md").read_text(encoding="utf-8")

    assert 'version = "0.5.1"' in pyproject
    assert "## [0.5.1]" in changelog
    assert "> version: `0.5.1`" in user_manual


def test_bootstrap_documentation_distinguishes_canonical_api_and_gate_shim() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    gate_verdict = (ROOT / "src" / "nirizan" / "gate" / "verdict.py").read_text(encoding="utf-8")

    assert "canonical `nirizan.metrics.stats.bootstrap_delta_ci`" in changelog
    assert "2-tuple wrapper" in changelog
    assert "deprecated 2-tuple shim" in gate_verdict
    assert "from nirizan.metrics.statistical_gating import bootstrap_delta_ci" in changelog


@pytest.mark.parametrize("module", OTEL_BRIDGE_MODULES)
def test_otel_bridge_public_names_are_documented_in_contract_docs(module: str) -> None:
    """L8 doc guard: contracts.md and architecture.md document every ``__all__`` name.

    These two documents are the stated source of truth for what each component
    promises. A name the bridge exports but neither document mentions is an
    undocumented public contract, so the guard reads ``__all__`` straight from
    source (via AST, never importing the optional ``opentelemetry`` modules)
    and requires it to appear in the contract documentation.
    """
    contracts = (ROOT / "docs" / "contracts.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    combined = f"{contracts}\n{architecture}"

    missing = [
        name for name in public_names(module) if not re.search(rf"\b{re.escape(name)}\b", combined)
    ]

    assert missing == [], (
        f"{module} exports {missing} but neither docs/contracts.md nor "
        "docs/architecture.md documents them"
    )


def test_the_doc_guard_covers_every_otel_bridge_module() -> None:
    """Guard the guard: no ``__all__``-bearing OTel bridge module is unchecked."""
    otel_dir = ROOT / "src" / "nirizan" / "instrumentation" / "otel"
    on_disk = {
        str(path.relative_to(ROOT / "src" / "nirizan")).replace("\\", "/")
        for path in otel_dir.glob("*.py")
        if "__all__" in path.read_text(encoding="utf-8")
    }

    assert on_disk == set(OTEL_BRIDGE_MODULES)


def _release_section(document: str, version: str) -> str:
    """The ``## ...version...`` section of ``document``, headings excluded."""
    lines = document.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.startswith("## ") and version in line),
        None,
    )
    assert start is not None, f"no release section for {version}"
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_contracts_document_the_zero_five_zero_breaking_change() -> None:
    """A breaking release needs a marked contracts section and a migration path.

    The Versioning Rule at the bottom of ``docs/contracts.md`` requires three
    things for a breaking change: a section titled with the release and marked
    as a breaking change, a stated migration path, and a version bump. The
    first two are checked here; the version bump is pinned by the release
    documentation test above.
    """
    contracts = (ROOT / "docs" / "contracts.md").read_text(encoding="utf-8")
    headings = [line for line in contracts.splitlines() if line.startswith("#") and "0.5.0" in line]

    assert headings, "docs/contracts.md has no section titled with release 0.5.0"
    assert all("Breaking Change" in heading for heading in headings)
    section = _release_section(contracts, "0.5.0")
    assert "**Migration path for callers:**" in section
    assert "**Migration path for persisted data:**" in section


def test_changelog_marks_the_zero_five_zero_breaking_entries() -> None:
    """The 0.5.0 changelog entry must label its breaking changes as breaking.

    ``CHANGELOG.md`` states that breaking changes on a ``0.x`` release are a
    minor bump and are called out explicitly, so a release that changes
    contract behavior has to say so in the same words the rule uses.
    """
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "**Breaking:**" in _release_section(changelog, "0.5.0")
