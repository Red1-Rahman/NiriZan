#!/bin/sh
# POSIX shell script: works with macOS /bin/sh, bash, and zsh; no GNU-only tools.
set -u
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd) || exit 2
cd "$repo_root" || exit 2
status=0

printf '%s\n' '=== Python security tests ==='
python3 -m pytest tests/security/ -v --tb=short || status=1

printf '%s\n' '=== Node workflow and findings checks ==='
if npm ci --prefix tests/security/js; then
    node tests/security/js/check-workflow-pins.cjs || status=1
    node tests/security/js/validate-findings-schema.cjs tests/security/js/known-findings.json || status=1
else
    status=1
fi
exit "$status"
