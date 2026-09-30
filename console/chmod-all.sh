#!/usr/bin/env bash
# NiriZan: make every shell script in the repository executable.
# Works on Linux (GNU tools) and macOS (BSD tools, bash 3.2).
#
# For files Git already tracks, it also records the executable bit in the
# index (git update-index --chmod=+x), so it survives a commit even on
# filesystems that do not keep permissions. It never commits or pushes.
#
# First run, before this file is executable itself:
#   bash console/chmod-all.sh
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

IN_GIT=0
if command -v git >/dev/null 2>&1 \
    && git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    IN_GIT=1
fi

total=0
changed=0

while IFS= read -r -d '' file; do
    rel="${file#"${REPO_ROOT}"/}"
    total=$((total + 1))

    if [[ ! -x "${file}" ]]; then
        chmod +x "${file}"
        echo "chmod +x   ${rel}"
        changed=$((changed + 1))
    fi

    if [[ "${IN_GIT}" -eq 1 ]]; then
        mode="$(git -C "${REPO_ROOT}" ls-files -s -- "${rel}" | cut -d' ' -f1)"
        if [[ -n "${mode}" && "${mode}" != "100755" ]]; then
            git -C "${REPO_ROOT}" update-index --chmod=+x -- "${rel}"
            echo "index +x   ${rel}"
            changed=$((changed + 1))
        fi
    fi
done < <(
    find "${REPO_ROOT}" \
        \( -name .git -o -name node_modules -o -name .venv -o -name venv \) -prune \
        -o -type f -name '*.sh' -print0
)

echo
echo "Checked ${total} shell script(s), ${changed} change(s)."
if [[ "${IN_GIT}" -eq 1 && "${changed}" -gt 0 ]]; then
    echo "Untracked scripts are executable on disk; stage them with:"
    echo "  git add --chmod=+x <file>"
fi
