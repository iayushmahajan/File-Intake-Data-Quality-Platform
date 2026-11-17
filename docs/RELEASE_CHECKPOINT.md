# Reconcile Workbench release checkpoint audit

Prepared **2026-11-17**. This records repository preparation and newly executed checks, not a
production release or a new AI/benchmark experiment. Earlier milestone and gallery reports remain
historical records with their own dates, environments and results.

## Starting point and publication scope

- Branch: `feat/reconciliation-workbench`.
- Starting HEAD: `6e89b94ab4bd40926b46c893f45cf8552351e860`.
- Initial working tree: 27 modified tracked files, 258 untracked files, nothing staged.
- Existing remote: `git@github.com:iayushmahajan/File-Intake-Data-Quality-Platform.git`.
- Read-only remote inspection: default branch `main` still at starting HEAD; the feature branch
  did not yet exist remotely. Publication targets only the corresponding feature branch.
- Strategy: one coherent full-stack checkpoint. Backend contracts/migrations, frontend callers,
  runtime configuration, tests and documentation are interdependent; splitting the accumulated
  implementation into arbitrary partial milestones would leave misleading intermediate states.
  The Git commit itself records the exact included file manifest.

No merge, force push, remote change, repository rename, visibility change or PR creation is part
of this checkpoint. Current feature-branch publication does not imply default-branch integration.

## Repository audit and file selection

The audit inventoried all 406 tracked/unignored candidate files, approximately 30.4 MB, including
unchanged files. It inspected tracked diffs, new source/test/configuration paths, file sizes/types,
symlinks, archive names, documentation links, screenshot metadata and credential patterns.

Included changes cover:

| Category | Intended content |
|---|---|
| Application source | Flights intake/persistence; deterministic normalization, grouping and evidence; bounded AI; human review/history; frozen exports; existing worker/legacy compatibility |
| Frontend | Routing, brand assets, design tokens, dataset/case/history features, contextual evidence, resizable source panels, review dialog and draft guards |
| Tests | Backend/API/migration and offline-evaluation tests; frontend behavior tests; synthetic browser fixtures/harness |
| Runtime/scripts | Dedicated Compose configuration and scoped launcher; dirty/reference inspection and frozen-output evaluation tools; existing CI adaptation |
| Documentation | Feature contracts, source manifest, setup/handoff, UX specifications, labeled validation reports and useful historical galleries |
| Small validation artifacts | Fictional synthetic observations, reviewed/exceptions CSVs and provenance demonstrating isolated persisted behavior; no database files |

The explicit staging manifest selects **285 changed/new files** after the exclusions below,
approximately 21.5 MB. No blanket `git add .` / `git add -A` is used. All existing source and
verification galleries are preserved. The six README images reuse existing files without copies.

Excluded and retained on disk:

- `docs/ui-review/live-workflow.zip`: 5,597,627-byte generated archive with 34 Markdown/PNG
  entries duplicating the expanded gallery. No unsafe archive traversal names were found.
- The untracked Windows `:Zone.Identifier` sidecar beside the approved logo reference.
- Private `.env.reconcile.local`, root/backend/frontend `.env` files: all ignored, mode 0600,
  and absent from the staging manifest. Values were not printed or copied.
- Runtime uploads/exports/databases, raw `dirty.csv` / `clean.csv`, virtual environments,
  `node_modules`, build output, TypeScript state, test caches/reports and temporary audit logs.

Ignore rules now explicitly cover the duplicate ZIP and download metadata. An old unchanged,
tracked legacy asset sidecar is preserved; ignore rules do not silently untrack existing files.
No existing file was deleted. Release edits update README, `.gitignore` and the stale CORS-origin sentence in
`docs/LOCAL_RUNTIME.md`, and remove one extra blank line at EOF from `CaseDetail.tsx`.
The new `.gitattributes` preserves exact CRLF bytes in the three synthetic evidence CSVs and
recognizes their line terminators during whitespace checking. The new checkpoint audit is the
sole newly authored document. No application behavior or runtime configuration was changed.

### Sensitive-data checks

Text-pattern findings were reviewed as placeholders, environment lookups or synthetic test
strings, not private credentials. The generated dedicated database password was compared with
candidate file bytes without printing it; no match was found. The already-public, explicitly
local-only legacy example password remains unchanged and is not a newly published private secret.
Private provider credentials are not staged. This is a scoped repository audit, not a formal
security certification or full historic Git secret scan.

No new symlinks, SQLite databases, runtime archives or oversized binary blobs entered the
manifest. The largest excluded file was the ZIP; the retained logo reference is approximately
1.07 MB. All **144 documentation PNGs** were inspected for EXIF/text metadata chunks; none
contained those chunks. The six selected screenshots were visually reviewed: public dirty-flight
identifiers/source reports and unsubmitted review controls, with no provider keys, private
customer information or clean-reference answers. Synthetic galleries are labeled as synthetic.
Dataset-specific rights remain uncertain as documented in `FLIGHTS_BENCHMARK.md`; limited
screenshots are not a grant of underlying redistribution rights. No raw benchmark was added.

## README and setup verification

The root README now explains the problem, implemented workflow, real stack, modular architecture,
local setup, tests, dataset provenance, evaluation boundary, limitations and project status.
It embeds/references Overview, Cases, focused desktop/mobile investigation, source evidence and
the current review dialog. All image paths are repository-relative. No hosted-demo URL or new
root license is invented; the existing UI MIT notice is retained.

Setup was checked against `scripts/reconcile.sh` and `compose.reconcile.yaml`: dedicated project,
three separate volumes, host frontend, loopback API, both localhost/127.0.0.1 CORS origins, empty
provider key and automatic startup migrations. `bash -n scripts/reconcile.sh` and
`bash scripts/reconcile.sh config` passed; the latter is quiet and does not start services.
No `init`, `up`, `start`, normal API startup or development-database migration was executed.
Migration tests used disposable databases only.

Relative README/documentation links and image references were checked locally. Remote object
availability must be confirmed after publishing. GitHub's visual Markdown rendering and CI
execution are separate from local path validation.

## Newly executed verification

| Check | Result |
|---|---|
| `timeout 180s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider -o faulthandler_timeout=45 backend/tests -q` | **294 passed**, 136.78s; includes disposable migration tests |
| `python3 -B -m unittest discover -s scripts -p 'test_flights_*.py' -q` | **24 passed**: benchmark foundation and offline evaluation |
| `pnpm --dir frontend test` | **191 passed**, 14 files |
| `pnpm --dir frontend build` | Passed; existing Browserslist data-age warning remains |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/home/ayush/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome pnpm --dir frontend test:foundation` | **46 checks passed**, Chromium 153, temporary frontend and synthetic APIs |
| `bash -n scripts/reconcile.sh` / `bash scripts/reconcile.sh config` | Passed; no service startup |
| `git diff --check` / `git diff --cached --check` | Passed after preserving CRLF evidence with scoped attributes and removing one extra blank EOF line |

The initial unstaged whitespace check did not inspect untracked files. Staging exposed CRLF
terminators in three frozen evidence CSVs and one extra component EOF blank line. Their artifact
bytes/hashes were preserved; the narrowly scoped attributes and EOF-only correction resolve the
checks without changing validation evidence or application behavior.

The first backend command, within the restricted execution sandbox, stalled after eight tests
and exited **124** at 180 seconds. The same isolated suite then completed outside that sandbox,
with a 45-second traceback watchdog and the same 180-second limit. This environmental failure is
recorded rather than hidden. `conftest.py` forces temporary SQLite/storage, memory transport and
an empty AI key before importing application modules. Disposable migration tests do not migrate
the retained development database.

Not run: Docker-backed integration/E2E, normal application launch, real-provider requests,
benchmark downloads, authentic reference evaluation, protected review/export writes or any new
live browser screenshot workflow. No existing database, volume, upload, review or export was
written by this task. Earlier isolated persisted-workflow evidence remains in
[Product validation](product-validation/milestone-1/REPORT.md); its results are historical and
are not presented as a newly repeated browser write-path test.

## Remaining review gates

Before merging, review the feature-branch diff and GitHub-rendered README/gallery, then run the
existing CI through an explicitly authorized pull request. Current workflow triggers on pull
requests and pushes to `main`; a feature push alone is not a claim that GitHub CI ran. Do not
merge solely because local tests pass. PostgreSQL concurrency/recovery, browser persisted writes,
real-provider usefulness, production access control, backup/restore and dataset rights remain
separately scoped validation/deployment topics. No code was added to resolve them in this task.
