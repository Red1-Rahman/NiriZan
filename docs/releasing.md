# Releasing NiriZan

This is the runbook for merging pull requests, bumping the version, and publishing a release. It is written for the maintainer and for AI coding assistants. An assistant given a task from this document must read it fully, follow it exactly, and stop at the points marked **STOP**.

## 1. Rules that never change

1. **Pull requests never bump the version.** Feature and fix branches keep the current version. The version changes only in the bump commit on `main` (section 4).
2. **The bump is one atomic commit on `main`.** Every file that carries the version changes in that single commit. A partial bump turns CI red.
3. **Bump first, then tag.** The release tag points at the bump commit and is created after it. A tag created before the bump would snapshot a codebase whose version documents disagree with the release, and that snapshot is what GitHub, PyPI, and Zenodo archive.
4. **The bump commit must be green locally before it is pushed.** The PyPI publish workflow runs when the Packaging workflow succeeds, and it does not wait for CI or Security. A red bump commit can therefore still publish to PyPI.
5. **PyPI versions are immutable.** A published version can be yanked but never replaced. Fix forward with a new version.
6. **Assistants never create tags or GitHub Releases, and never push.** The maintainer does these steps by hand.
7. **Zenodo versions are permanent.** Files and DOIs cannot be removed once a version is published. Only publish GitHub Releases for versions that should be archived.

## 2. How the pipelines connect

| Workflow | Trigger | What it does | Release relevance |
|---|---|---|---|
| `ci.yml` | push and pull request on `main` | pytest on a matrix (core only and with the `otel` extra, Python 3.11 and latest), mypy, import-linter | Must be green on the bump commit |
| `security.yml` | push and pull request on `main`, weekly | AST security tests, VirusTotal, GuardDog, Bandit, Semgrep, CodeQL, pip-audit, OSV, Trivy, Gitleaks, Zizmor, SBOM | `pip-audit` excludes the local `nirizan` wheel, so a new unpublished version does not break it |
| `packaging.yml` | see note below | Builds the distributions and uploads the `python-distributions` artifact | Its success triggers the PyPI publish |
| Publish to PyPI | `workflow_run` of Packaging, branch `main`, on success | Downloads the artifact, checks exactly one wheel and one sdist, skips if the version already exists on PyPI, otherwise publishes through Trusted Publishing | A push to `main` can publish without CI or Security passing |
| `zenodo.yml` | GitHub Release published, not a pre-release | Validates metadata, skips if the version exists on Zenodo, builds the source zip, wheel and sdist, creates a new Zenodo version, uploads, publishes. Runs share one concurrency group with `queue: max`, so up to 100 pending runs wait their turn and none is cancelled | Gated by the `zenodo` environment and a required reviewer |
| `cross-platform.yml`, `scorecard.yml` | see note below | Cross-platform tests and supply-chain scoring | Their badges appear in the README |
| dependency graph workflow | manual only | Regenerates `docs/dependency-graph.md` | Not part of a release |

**Note for assistants:** the table is a summary written from partial knowledge. The trigger details of `packaging.yml`, `cross-platform.yml`, `scorecard.yml`, and the dependency graph workflow were not verified when this document was written. Before any bump or release task, read every file in `.github/workflows/` and `.github/scripts/` and report anything that contradicts this table. If the files and this document disagree, the files win, and this document should be corrected in the same change.

### README badges

The README shows live badges for CI, Packaging, Cross-platform, Security, and Scorecard. PyPI renders the README text as it was at upload, but the badge images load live and may be cached. A red badge on `main` can appear on the PyPI project page. This is another reason the bump commit must be green before it lands, and why any README change (for example a new badge) belongs in the bump commit or earlier, never after the release.

## 3. Merging a pull request

1. Confirm CI and Security are green on the pull request.
2. Confirm the pull request does not change the version. If it does, remove the change and move it to the bump commit.
3. If the change is user-visible, add an entry under an `Unreleased` heading in `CHANGELOG.md`, or note the entry in the pull request description, so it can be moved into the bump commit.
4. If the change is breaking, add a section to `docs/contracts.md` titled with the release it ships in and marked **Breaking Change**, with a migration path, as the Versioning Rule at the bottom of that file requires.
5. Merge. Do not bump or tag as part of the merge.

## 4. Version bump (one atomic commit on `main`)

### Choosing the version

NiriZan is on `0.x`. Following `docs/contracts.md` and `CHANGELOG.md`:

- A breaking change to a contract is a **minor** bump (`0.5.x` to `0.6.0`).
- A backward-compatible feature or fix is a **patch** bump (`0.5.3` to `0.5.4`).
- Releases that change no runtime behavior (documentation, CI, metadata) are patch bumps.

### Files that carry the version

| File | Change |
|---|---|
| `pyproject.toml` | `[project] version` |
| `src/nirizan/__init__.py` | `__version__` and anything else that duplicates the version |
| `CITATION.cff` | `version` and `date-released`, both as quoted strings |
| `CHANGELOG.md` | New `## [X.Y.Z] - YYYY-MM-DD` section above the previous one, plus a link reference at the bottom |
| `SECURITY.md` | Latest released version and its release date, wherever they appear, including the supported versions table |
| `README.md`, `docs/` | Only references to the current version, if any. Do not add version numbers where none exist |

Do not edit historical changelog entries, release-specific sections of `docs/contracts.md`, the generated `docs/dependency-graph.md`, or `.zenodo.json` (it has no version field by design).

`date-released` is the UTC day the GitHub Release will be published. The Zenodo workflow stamps the publication date as the UTC day it runs, so the two should match.

### Procedure

1. Start from an up-to-date `main` with a clean working tree.
2. Run `git grep -nF "<OLD_VERSION>"` and list every hit.
3. Make the edits from the table above.
4. Verify locally:
   ```bash
   python .github/scripts/check_zenodo_metadata.py
   pip install -e ".[dev,otel]"
   pytest -rs
   mypy
   lint-imports
   ruff check .
   python -c "import nirizan; print(nirizan.__version__)"
   python -m build
   ```
   The metadata check must print `Metadata OK, version <NEW_VERSION>`. The printed package version must equal the new version. Both the wheel and the sdist filenames must contain the new version.
5. Run `git grep -nF "<OLD_VERSION>"` again. Every remaining hit must be historical, and each one must be explained.
6. Commit once, with the message `chore(release): bump version to <NEW_VERSION>`.
7. **STOP.** Do not push. The maintainer reviews `git show --stat HEAD` and pushes.

## 5. Publishing the release

Done by the maintainer, by hand, after the bump commit is pushed.

1. Wait for `ci.yml`, `security.yml`, and Packaging to finish on the bump commit. All must be green.
2. Confirm the Publish to PyPI run succeeded and the new version appears at https://pypi.org/project/nirizan/.
3. Create the GitHub Release:
   - Tag: `v<NEW_VERSION>`, using **Create new tag on publish**.
   - Target: the bump commit (select its SHA, not just `main`, if `main` has moved on).
   - Not a draft and not a pre-release. The Zenodo workflow ignores pre-releases.
   - Notes: the new `CHANGELOG.md` section.

   With the CLI:
   ```bash
   gh release create v<NEW_VERSION> --target <BUMP_COMMIT_SHA> --title "v<NEW_VERSION>" --notes-file release-notes.md
   ```
   Create the release as yourself, not from a workflow using `GITHUB_TOKEN`, because such a release does not trigger other workflows.
4. Open the Actions tab. The `zenodo` run waits for approval. Before approving, open the lookup step log and check that `latest_id` is the ID of the previous published Zenodo version. For the first automated release this is `23448538`.
5. Approve the run.

## 6. After the release

1. Zenodo: the new version shows the source zip, wheel, and sdist, with the right version and date. Compare title, affiliations, related works, license, and keywords with `.zenodo.json`.
2. Zenodo: the version DOI is new, and the concept DOI (`10.5281/zenodo.23448537`) is unchanged.
3. GitHub: the release page shows the correct tag and notes, and the source archive contains the new version in `pyproject.toml`.
4. PyPI: the project page renders correctly and the badges are green.
5. If the paper cites this release, record the version DOI in the reproducibility notes.

## 7. When something goes wrong

| Situation | Action |
|---|---|
| Bump commit is red after push | Do not tag. If PyPI already published, the version is spent. Fix forward with the next patch version, as releases 0.5.1 to 0.5.3 did. Yank the bad version on PyPI only if it is broken for users |
| Tag created before the bump | Delete the release and the tag before the Zenodo workflow is approved, then bump and tag again. If Zenodo already archived it, fix forward with a new version |
| Release tag does not match `pyproject.toml` | The Zenodo metadata check fails before anything is uploaded. Delete the tag and release, correct the bump, and tag again |
| Zenodo run fails after the draft was created | Discard the unpublished draft in the Zenodo UI, then re-run the workflow. The existence check makes re-runs safe |
| Zenodo run is skipped | The release was a draft or a pre-release, or it was created by a workflow token. Publish a normal release by hand |
| Several releases published in quick succession | The workflow uses `queue: max`, so pending runs wait for the active one and none is replaced. Each run looks up the latest published version when it starts, so the order is safe. Approve them one at a time. If GitHub or Zizmor rejects the `queue` key, remove it, and re-run any run that shows as cancelled |
| `ZENODO_CONCEPT_ID` error | The variable is missing from the `zenodo` environment, or the first record is not published |

