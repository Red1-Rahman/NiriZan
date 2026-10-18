---
description: Prepare the patch version bump commit (X.Y.Z to X.Y.Z+1)
agent: agent
---
Prepare the **patch** bump commit. Follow [docs/releasing.md](../../docs/releasing.md) sections 1 and 4 exactly.

Inputs: old version from `pyproject.toml`; new version = patch + 1; release date = ${input:date:YYYY-MM-DD, UTC day of the release}.

Stop and report, without editing, if any of these fail:
- The tree is dirty, or `main` is not up to date.
- `[Unreleased]` in `CHANGELOG.md` contains a breaking entry.

Steps:
1. Run `git grep -nF "<old>"` now and again at the end. Explain every remaining hit.
2. In `CHANGELOG.md`, rename `[Unreleased]` to `[<new>] - <date>`, add an empty `[Unreleased]` above it, and update the link references. If it was empty, add a one-line entry.
3. Update every other file in the section 4 table.
4. Run the section 4 checks.
5. Make one commit: `chore(release): bump version to <new>`.

Read `.github/workflows/` only if `git diff --stat v<old>..HEAD -- .github` is not empty.
Never push, tag, or create a release. Reply in 15 lines or fewer: changed files, check results, anything uncertain.
