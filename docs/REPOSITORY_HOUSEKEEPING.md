# Repository artifact and branch audit

**2026-11-17**. Documentation/artifact housekeeping only; no application, test, CI, runtime,
provider, database or migration behavior changes. No branches or worktree registrations deleted.

## Baseline and classification

Initial branch `feat/reconciliation-workbench`, HEAD
`e406204cafe12e379600436ae24f9c152d35d914`, clean index/worktree.
Remote `origin` remains `git@github.com:iayushmahajan/File-Intake-Data-Quality-Platform.git`.
All five advertised remote branch tips matched their local/remote-tracking counterparts.
GitHub's open-pull-request endpoint returned an empty list.

The audit inventoried **406 tracked files**, including **164 image assets**, and two explicit
ignored disposal candidates. Categories: backend 105 files, frontend 88, documentation 188,
scripts 9, legacy assets 7, and 9 root/editor/CI/configuration files. It inspected screenshot
indexes, README image dependencies, references from code/tests/scripts, ignore rules, synthetic
versus live evidence provenance, branch ancestry and registered worktrees.

| Classification | Treatment |
|---|---|
| Keep | Six final product images; approved logo source and production brand assets; all source, tests, required fixtures, infrastructure and CI; architecture/benchmark/runtime/release docs; UX specification/plan; controlled E2E proposal; complete product-validation evidence; final interaction-result JSON |
| Remove from active branch | 134 superseded PNGs, two redundant early viewport-check reports, one tracked download-metadata sidecar; exact duplicate local ZIP and an ignored logo download sidecar |
| Needs review / retained | Legacy `assets/screenshots/`, `docs/images/`, original frontend assets and unrelated existing engineering material: their retirement is outside this clearly identified UI-gallery cleanup. Ignored runtime data, installed environments, build outputs/caches and test outputs were left alone rather than purged. |

The ZIP's **28 regular files** matched expanded files byte-for-byte (34 entries including
directories). It had no unique evidence to preserve. No `git clean`, cache sweep, deletion
outside the repository, history rewrite, garbage collection or volume operation was used.

## Exact removal categories

The counts below exclude six byte-identical moves to the stable product directory.

| Directory | Files removed | Category |
|---|---:|---|
| `docs/screenshots/` | 5 | Original default/legacy UI captures |
| `docs/screenshots/refinement-2026-11-13/` | 40 | 38 intermediate/synthetic PNGs and 2 redundant check JSONs |
| `docs/ui-review/investigate-redesign/checkpoint-1/` | 6 | Superseded PNGs |
| `docs/ui-review/investigate-redesign/checkpoint-2/` | 9 | Superseded PNGs |
| `docs/ui-review/investigate-redesign/checkpoint-3/` | 12 | Superseded PNGs |
| `docs/ui-review/investigate-redesign/checkpoint-4/` | 14 | Superseded PNGs |
| `docs/ui-review/layout-and-contextual-details/` | 15 | Supplemental PNGs; four final images moved |
| `docs/ui-review/live-workflow/` | 27 | Old three-column workflow captures across five subdirectories |
| `docs/ui-review/panel-and-review-interactions/` | 8 | Supplemental PNGs; two final images moved; JSON evidence retained |
| `assets/` | 1 | Tracked `:Zone.Identifier` download metadata only; image preserved |
| **Tracked total** | **137** | **18,460,169 bytes** of obsolete file contents |

Two additional **ignored local-only files** were removed explicitly: `docs/ui-review/live-workflow.zip`
and the logo-reference `:Zone.Identifier`, totaling **5,597,652 bytes**. These have no tracked
Git deletion and are not included in the 137 count. Together the removed files occupied about
**24.1 MB / 22.9 MiB** before the small documentation adjustments. Six image moves do not count
as size reduction. Git's historical blobs remain; this does not promise a smaller full-history clone.

## Product gallery and documentation

The six original README images now exist once in [screenshots/product](screenshots/product/README.md):

- `dataset-overview.png`
- `cases-table.png`
- `focused-case.png`
- `source-evidence.png`
- `human-review-dialog.png`
- `mobile-investigation.png`

Their SHA-256 values match the pre-cleanup originals. No image was generated, recompressed or
replaced with a mockup. Original capture dates, dimensions, dirty-only data provenance and
unsubmitted-review status remain explicit. The approved logo reference was preserved unchanged.

The root README only changes image paths and the gallery-link label. Screenshot indexes now
point to the product collection or concise historical findings. Checkpoint summaries retain
real-data totals, pagination/deep-link behavior, review/AI distinctions, historical test results,
safety checks and limits. The initial populated audit preserves the measured overcrowding that
motivated the redesign. The current layout and panel-interaction reports retain their detailed
measurements; only obsolete screenshot tables were replaced. The UX plan's preservation note
now points to the retained audit/Git history rather than requiring retired captures to stay active.

Original intermediate screenshots and full reports remain recoverable at commit `e406204`.
The [release checkpoint](RELEASE_CHECKPOINT.md) and all of
[Product-validation Milestone 1](product-validation/milestone-1/REPORT.md) remain byte-identical;
statements in those historical audits describe their own dates, not this cleanup.

Existing ignore rules already cover local environment files, build/cache/test outputs,
benchmark CSVs, download metadata and the duplicate ZIP. No broader ignore pattern was added;
only the ZIP-rule comment was corrected after its local removal.

## Verification performed for housekeeping

- Explicit deletion/move manifest was checked before removal. No removed artifact is required by
  application code, tests or scripts. No test fixture, validation CSV/JSON or executable was removed.
- SHA-256 comparison proves **220 protected paths**, covering backend/frontend/source/test/script/CI/runtime paths and
  `docs/product-validation/milestone-1/` are unchanged. The six moved images match their originals.
- **35 active Markdown documents / 103 relative links** passed existence checks, with no broken links. Markdown code
  fences, README disclosure tags and the six PNG signatures/chunks/CRCs/decompressed image data
  were checked. Source image bytes are unchanged; GitHub object paths are checked after publication.
- `git diff --check` and staged-diff checks passed. No frontend/backend/browser suites were rerun:
  source, required fixtures and runtime assets did not change; this is documentation-only cleanup.
- No live API request, upload, AI call, review, export, migration, Docker operation or runtime write
  was performed. No new screenshots or synthetic test records were created.

## Branch audit — read-only, deletion not executed

Counts are relative to the **initial feature HEAD `e406204`**, not to `main`: unique branch commits /
feature-only commits. The cleanup adds one feature commit, increasing each older branch's behind
count by one; it does not introduce unique work into those branches.

| Branch | Local / remote | Tip | Unique / behind | All commits reachable from feature | Open PR | Branch checked out in worktree | Classification |
|---|---|---|---|---|---|---|---|
| `main` | Both | `6e89b94ab4bd40926b46c893f45cf8552351e860` | 0 / 2 | Yes | No | No | **Keep**, default branch |
| `feat/reconciliation-workbench` | Both | `e406204cafe12e379600436ae24f9c152d35d914` before cleanup | 0 / 0 | Current branch | No | Main repository | **Keep**, active unmerged work |
| `chore/repository-checkpoint` | Both | `0b3ebe20428da2af6ee74f767101022cad1d642b` | 0 / 6 | Yes | No | No | **Safe deletion candidate** |
| `fix/correction-draft-navigation` | Both | `62ffb91a39c3919df0b52d62645d8d2e870f112f` | 0 / 3 | Yes | No | No | **Safe deletion candidate** |
| `refactor/feature-architecture` | Both | `17637fbbccf78abdd66536d6cd712e83a91ce678` | 0 / 8 | Yes | No | No branch checkout; see detached metadata below | **Safe deletion candidate** |

The three older branches' tips are also reachable from `main`. They contain no unmerged/unique
commits relative to the feature branch. Removing those refs would not remove current code/history;
the active feature branch must remain until separately reviewed and merged.

`git worktree list --porcelain` shows the current repository on the feature branch and a **stale,
detached** record at `/tmp/file-intake-publish-review`, commit `17637fb`. Git marks its missing
location prunable. No branch is checked out there; the detached commit matches the refactor tip
and remains reachable. That registration was not pruned or modified. Its former workspace
ownership/value should be reviewed separately; no filesystem operation outside this repo occurred.

### Proposed commands — NOT executed; separate approval required

Recheck remote tips, ancestry, worktrees and open PRs immediately before any future deletion.
From the retained feature branch, normal local deletion candidates are:

```bash
git branch -d chore/repository-checkpoint
git branch -d fix/correction-draft-navigation
git branch -d refactor/feature-architecture
```

Corresponding remote deletion candidates are:

```bash
git push origin --delete chore/repository-checkpoint
git push origin --delete fix/correction-draft-navigation
git push origin --delete refactor/feature-architecture
```

Do not add `main` or `feat/reconciliation-workbench`, use `-D`/force, or execute any of these
commands under this housekeeping authorization. No PR, merge, rebase or repository setting change
is part of this task. Review the feature branch before authorizing merge or branch retirement.
