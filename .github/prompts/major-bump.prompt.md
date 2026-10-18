---
description: Prepare the major version bump commit (1.0.0 and later)
agent: agent
---
Prepare the **major** bump commit. Follow [docs/releasing.md](../../docs/releasing.md) sections 1 and 4 exactly.

Inputs: old version from `pyproject.toml`; new version = major + 1, minor 0, patch 0; release date = ${input:date:YYYY-MM-DD, UTC day of the release}; confirmation = ${input:confirm:Type YES to confirm the public contract surface is stable}.

Stop and report, without editing, if any of these fail:
- The confirmation is not exactly `YES`. The move to 1.0.0 is reserved for a stable public contract surface.
- The tree is dirty, or `main` is not up to date.
- `[Unreleased]` has a breaking entry but `docs/contracts.md` has no **Breaking Change** section for `<new>` with a migration path.

Steps:
1. Run `git grep -nF "<old>"` now and again at the end. Explain every remaining hit.
2. In `CHANGELOG.md`, rename `[Unreleased]` to `[<new>] - <date>`, add an empty `[Unreleased]` above it, and update the link references.
3. Update every other file in the section 4 table.
4. Apply the 1.0 wording changes, and list each one in the reply for my review:
   - `pyproject.toml`: Development Status classifier to `5 - Production/Stable`.
   - `CHANGELOG.md` intro: replace the 0.x rule with "breaking changes require a major version bump".
   - `SECURITY.md`: remove "pre-1.0" statements. Leave the supported-versions policy text unchanged and flag it.
5. Run the section 4 checks.
6. Make one commit: `chore(release): bump version to <new>`.

Read `.github/workflows/` only if `git diff --stat v<old>..HEAD -- .github` is not empty.
Never push, tag, or create a release. Reply in 20 lines or fewer: changed files, check results, items for review.
