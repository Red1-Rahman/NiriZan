---
description: Prepare the minor version bump commit (X.Y.Z to X.Y+1.0), a breaking release while on 0.x
agent: agent
---
Prepare the **minor** bump commit. Follow [docs/releasing.md](../../docs/releasing.md) sections 1 and 4 exactly.

Inputs: old version from `pyproject.toml`; new version = minor + 1, patch 0; release date = ${input:date:YYYY-MM-DD, UTC day of the release}.

While on 0.x a minor bump is the breaking release. Stop and report, without editing or writing the missing parts yourself, if any of these fail:
- The tree is dirty, or `main` is not up to date.
- The major version is 1 or higher (ask me what a minor bump means then).
- `[Unreleased]` has no breaking entry.
- `docs/contracts.md` has no **Breaking Change** section for `<new>` with a migration path.

Steps:
1. Run `git grep -nF "<old>"` now and again at the end. Explain every remaining hit.
2. In `CHANGELOG.md`, rename `[Unreleased]` to `[<new>] - <date>`, add an empty `[Unreleased]` above it, and update the link references.
3. Update every other file in the section 4 table.
4. Run the section 4 checks.
5. Make one commit: `chore(release): bump version to <new>`.

Read `.github/workflows/` only if `git diff --stat v<old>..HEAD -- .github` is not empty.
Never push, tag, or create a release. Reply in 15 lines or fewer: changed files, check results, anything uncertain.
