#!/usr/bin/env bash
# NiriZan dependency graph generator (Linux, GNU tools).
# Regenerates docs/dependency-graph.md locally.
# Never commits, pushes, or stages anything.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
GENERATOR="${REPO_ROOT}/.github/scripts/gen_dependency_graph.py"
OUTPUT_REL="docs/dependency-graph.md"
VERSION_CHECK='import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'

if [[ ! -f "${GENERATOR}" ]]; then
    echo "Error: dependency graph generator not found: ${GENERATOR}" >&2
    exit 1
fi

# Pick the first interpreter that is actually Python 3.11 or newer
# (CI uses 3.11), instead of trusting whatever "python3" resolves to.
PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1 \
        && "${candidate}" -c "${VERSION_CHECK}" >/dev/null 2>&1; then
        PYTHON="${candidate}"
        break
    fi
done

if [[ -z "${PYTHON}" ]]; then
    echo "Error: Python 3.11 or newer is required (CI uses 3.11)." >&2
    exit 1
fi

"${PYTHON}" "${GENERATOR}"

# Read-only summary. Skipped when git is missing or this is not a checkout.
if command -v git >/dev/null 2>&1 \
    && git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    changes="$(git -C "${REPO_ROOT}" status --short -- "${OUTPUT_REL}")"
    echo
    if [[ -n "${changes}" ]]; then
        echo "${changes}"
        echo "Review with: git diff -- ${OUTPUT_REL}"
    else
        echo "No changes: ${OUTPUT_REL} is already up to date."
    fi
fi
