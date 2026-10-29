# tests/security/test_supply_chain_static.py
"""Static checks over GitHub Actions workflow source."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# GitHub Actions accepts both .yml and .yaml for workflow files; scanning only
# *.yml silently skips any workflow using the .yaml extension.
WORKFLOW_PATTERNS = ("*.yml", "*.yaml")


def _workflow_paths():
    paths = []
    for pattern in WORKFLOW_PATTERNS:
        paths.extend((ROOT / ".github/workflows").glob(pattern))
    return sorted(set(paths))


def test_workflow_action_refs_are_full_sha_pinned():
    issues = []
    for path in _workflow_paths():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = re.search(r"\buses:\s*([^\s#]+)", line)
            if match and not re.search(r"@[0-9a-fA-F]{40}$", match.group(1)):
                issues.append(f"{path.name}:{number}: {match.group(1)}")
    assert not issues, "Unpinned actions:\n" + "\n".join(issues)


def test_privileged_workflows_do_not_install_unpinned_packages_before_publish():
    issues = []
    for path in _workflow_paths():
        text = path.read_text(encoding="utf-8")
        if "id-token: write" in text:
            for n, line in enumerate(text.splitlines(), 1):
                if re.search(r"\bpip install\b", line) and not re.search(r"--require-hashes|@[0-9a-f]{40}", line):
                    issues.append(f"{path.name}:{n}: {line.strip()}")
    assert not issues, "Unpinned installs in id-token jobs:\n" + "\n".join(issues)


def test_write_permission_checkout_disables_persisted_credentials():
    issues = []
    for path in _workflow_paths():
        text = path.read_text(encoding="utf-8")
        if not re.search(r"(?:contents|pull-requests):\s*write", text):
            continue
        for block in re.findall(r"(?ms)^\s*- uses:\s*actions/checkout@.*?(?=^\s*- |\Z)", text):
            if "persist-credentials: false" not in block:
                issues.append(f"{path.name}: checkout under write permissions lacks persist-credentials: false")
    assert not issues, "Unsafe checkout configuration:\n" + "\n".join(issues)


def test_workflow_run_branch_filter_review_notice(capsys):
    notices = []
    for path in _workflow_paths():
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if re.match(r"\s*workflow_run:\s*$", line):
                block = "\n".join(lines[i:i + 12])
                if "branches:" in block and "head_repository.full_name" not in "\n".join(lines):
                    notices.append(f"{path.name}: workflow_run branches filter needs manual review")
    print("\n".join(notices))