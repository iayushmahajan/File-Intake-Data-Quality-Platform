# Validation status and engineering checkpoints

This is the current verification map, consolidated **2026-11-17**. Results below are dated records,
not tests rerun by documentation cleanup. Passing isolated tests does not establish production
readiness, real-provider effectiveness or PostgreSQL concurrency correctness.

## What has actually been verified

| Boundary | Evidence and limits |
|---|---|
| Deterministic intake, normalization, grouping, candidates, baseline, review/history and exports | Synthetic unit/API fixtures with temporary SQLite/storage and memory transport; real backend handlers exercised |
| Responsive frontend, navigation, dialogs, drafts and synthetic write-path presentation | Vitest/Testing Library and isolated Playwright/Vite with intercepted fictional APIs; not proof of live persistence |
| Real-data read-only frontend/API | Existing dirty Flights import 5, desktop/mobile Chromium, actual API responses, no fabricated AI/review results |
| Dedicated runtime | PostgreSQL/Redis/API/worker/dispatcher health and migration head 0006 were observed; five completed imports/11,880 observations were preserved during prior read-only checks |
| Persisted human workflow | Actual in-process API and independent SQLite readback, synthetic data, immutable source rows and frozen artifact hashes; detailed evidence below |
| Offline methodology | Synthetic manifest/reference fixtures, integrity checks and metric denominators; no authentic frozen benchmark repair score |

The original File Intake environment was retained separately. Historical transaction-stack
verification (2026-10-02) exercised disposable PostgreSQL/Redis/Celery API restart, broker message
loss, duplicate delivery and worker-child death, including recovery and missing outputs. That does
not verify current Flights-specific races, recovery or production rollout.

## Latest completed regression checkpoint

The release preparation on **2026-11-17**, commit `638eefa`, completed:

| Command/check | Result |
|---|---|
| `timeout 180s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider -o faulthandler_timeout=45 backend/tests -q` | **294 passed**, 136.78s; migrations used disposable databases |
| `python3 -B -m unittest discover -s scripts -p 'test_flights_*.py' -q` | **24 passed**, benchmark foundation plus evaluation |
| `pnpm --dir frontend test` | **191 passed**, 14 files |
| `pnpm --dir frontend build` | Passed; existing Browserslist data-age warning retained |
| `pnpm --dir frontend test:foundation` with an existing Chromium executable | **46 route/viewport checks** plus interactions, Chromium 153; synthetic APIs only |
| Launcher shell syntax / quiet resolved config / whitespace | Passed without service startup |

The first restricted-sandbox backend run stalled after eight tests and exited 124 at 180 seconds;
the isolated rerun outside that sandbox is the completed passing evidence. Earlier interrupted
runs are not counted as successful. Existing CI runs backend/frontend checks and a separate
state-changing async integration job on PRs/main pushes; a feature push alone does not prove
GitHub CI passed. Commands and fixture isolation are documented in [development](DEVELOPMENT.md).

## Persisted review/history/export validation

The unchanged [Product-validation Milestone 1 report](product-validation/milestone-1/REPORT.md)
and [runner](product-validation/milestone-1/verify_workflow.py) record **2026-11-16** behavior against
a pre-existing, separately verified empty 0006 SQLite test database. There was no mock API response.
Owner/mode, symlink/hardlink status, no open-file owner, mount separation, schema/revision and
zero starting rows were checked before writes. SQLite opened in mode=rw to forbid accidental
creation; SQL/provider/socket guards prevented schema changes, deletions and protected-row updates.
No Celery transport or normal application lifespan was needed.

- Seven fictional reports across three flights covered conflicting clocks with repeated same-source
  reports, missing versus placeholder data, and equivalent supported clocks. A deliberately supported
  09:00 selection was a human judgment, not benchmark reference truth.
- **36 real API checks** passed, including exact retries and expected 409 conflicts for changed
  request payload, stale revision and stale evidence. Re-review preserved earlier events.
- Independent sessions/processes retrieved **four append-only review events** (two supported-value
  revisions and two unresolved revisions) with exact identity, attribution, rationale and request IDs.
- One frozen export contained three flight rows, exactly **one approved field**, and **11 exceptions**.
  Unreviewed, conflicting or unresolved values were not silently approved. Provenance mapped each
  field back to its actual synthetic observation cells.
- All artifact sizes/SHA-256 matched metadata; fixed snapshot/UUID/time re-rendered byte-identically.
  A later unresolved revision changed the current snapshot; stale new export creation was rejected,
  while the original export/retry/downloads remained byte-identical.
- Original input/status and all seven complete observation rows stayed unchanged. Independent
  readback verified immutability and schema 0006. Five protected imports, 11,880 observations,
  fingerprints and container identities were unchanged during that run.

All [evidence files](product-validation/milestone-1/evidence/results.json), CSVs, metadata,
provenance and the runner retain their original paths/bytes. The report's then-zero AI/review/export
counts are dated baseline measurements, not today's live totals. The runner is a guarded record
of one controlled run, **not** a reusable public demo command: it refuses nonempty databases/existing
output and requires separately verified isolated resources. Do not rerun it against development.
Browser-level persisted writes, paid AI and authentic reference evaluation were not verified by it.

## UI interaction evidence

Current screenshots live in the [product gallery](screenshots/product/README.md). They are genuine
read-only captures, not generated mockups or persisted-review proof. Source/raw/normalized values
remain accessible without displaying all records at once; no majority-as-truth or invented progress.

The **2026-11-16** native interaction run preserves
[scroll/resize/touch measurements](ui-review/panel-and-review-interactions/interaction-results.json)
and [navigation-guard results](ui-review/panel-and-review-interactions/navigation-results.json)
at their original paths. A 550px wheel over a source table advanced its dialog body from 0 to 550,
while background position stayed 552px; earlier inner overscroll containment had prevented that.
The final outer body retains modal scroll containment. Actual edge dragging reached 1,236/680px;
keyboard End/ArrowRight/Home reached 1,280/1,248/680px. Paging reached all 21 records. Native CDP
touch events scrolled expanded mobile evidence at 390px and 320px without document overflow.

Review checks exercised untouched close, Continue/Keep draft/Resume/Discard, browser Back and
Next-case guards, single-modal focus and restored form input. No live submission was made.
Twenty-four API requests in the interaction run were all GET; four existing AI investigation rows,
zero reviews/exports, five imports, 11,880 observations and their fingerprint were preserved.
Physical trackpads, mobile software keyboards, Safari/iOS and comprehensive assistive-technology
coverage remain unverified. Best-effort unload guards do not recover drafts after forced termination.

## Outstanding validation gates

### PostgreSQL, transport and rollout

Require a separately approved disposable PostgreSQL cluster/role/database with unique identity,
ports, volumes, broker/queue and storage. Never adopt development resources because tests passed.
Inspect actual database/user/server address/revision and require empty scratch state; use an
explicit scratch engine/Alembic connection, not application startup. The standard pytest conftest
always selects SQLite even if DATABASE_URL is supplied.

Seed synthetic legacy state at 0003, upgrade sequentially to 0004–0006 and compare rows/files.
Reuse preservation assertions from `backend/tests/test_migrations.py`, `test_flight_investigations.py`
and `test_flight_review_exports.py`. Verify PostgreSQL foreign/check constraints, tuple/position
uniqueness and index byte limits, JSON NULL handling, partial running-scope/charged-attempt indexes
and nullable unique claim slots. A migration-only probe is not a full concurrency test.

Use independent connections to verify `SELECT ... FOR UPDATE` blocks the second writer (a local
500ms lock_timeout should fail until the first commits); roll back failures before reuse. Then
exercise actual review/export functions: one stale-revision winner, one exact retry event and a
coherent export vector or explicit stale rejection. Test READ COMMITTED visibility, lock timeouts,
deadlocks, connection/acknowledgement loss, two-slot/three-attempt claim races with a fake provider,
expired-token fencing and provider work outside transactions. Separately verify Redis/Celery
loss/duplicates/lease recovery and file-publication ambiguity in scratch storage. Record ownership,
then retire only approved scratch resources. No broad cleanup is authorized by this plan.

Before retained-data rollout, restore a coordinated database+file backup, verify preservation and
obtain target-specific approval as described in [development](DEVELOPMENT.md). Production access
control, hosting/SPA fallback, backup/restore and interrupted-operation handling remain gates.

### Controlled AI and persisted browser journey

Prove separate writable resources before any upload/review/export. An existing temporary database
may have disappeared or been reused; verify its identity/owner/schema/emptiness again. Never point
a browser at the five protected imports to populate screenshots. If no isolated HTTP backend/frontend
exists, report browser persistence unverified rather than substituting intercepted responses.

For AI, approve provider/model parameter compatibility, current pricing, retention/privacy and a
spending ceiling; configure ignored secrets only for the isolated process. Start with **one explicit
request**, no automatic retry, with an eligible dirty-only case and frozen candidate/digest/baseline.
Record usage, latency, valid citations, useful explanation and uncertainty or justified abstention.
A provider failure is a truthful outcome, not evidence of model value. Compare later controlled cases
with the deterministic baseline; see [AI/evaluation](AI_AND_EVALUATION.md). No reference answers,
dirty/reference comparison reports or independently corrected examples enter the operational prompt.

In an authorized browser run, document one source-supported decision and a separate unresolved
outcome, reload/current/history attribution and revision checks, create one frozen export and verify
all three downloaded artifact hashes/cell mappings. Compare original input/observation fingerprints
before/after; demonstrate later review cannot mutate the frozen result. Only **after freezing** may a
separate offline process receive the reference. The existing evaluator measures reviewed exports,
not direct AI-versus-baseline suggestion performance. No authentic frozen benchmark result is claimed.

## Dated repository and product checkpoints

| Date / recoverable Git reference | Important conclusion |
|---|---|
| 2026-11-11, pinned manifest | Dirty/reference integrity and research lineage recorded; no repair performance or underlying rights clearance |
| 2026-11-12–16, implementation/UX milestones | Fixed Flights pipeline, Overview → Cases → focused detail, complete mobile evidence, current review/dialog/draft safeguards; no arbitrary schema or verified-truth badge |
| 2026-11-16, product-validation report | Real persisted isolated SQLite decisions/history/export/immutability; no browser-write/provider verification |
| 2026-11-17, `638eefa` | Full-stack release checkpoint; completed regression results above; private env/runtime/raw benchmarks excluded; no root license invented |
| 2026-11-17, `e406204` | One-line obsolete Vercel default removed; five config-only checks passed; 5174 override unaffected |
| 2026-11-17, `77c3071` | 137 obsolete tracked artifacts retired, six unchanged screenshots curated, useful findings retained; 103 relative links checked; no branches deleted |
| 2026-11-17, documentation consolidation | 55 files / 31 Markdown / 21 subdirectories reduced to 28 / 7 / 7, with five primary guides; evidence/manifest/image bytes preserved; local links/anchors and protected hashes checked, no application suites rerun |

Prior complete milestone, release and housekeeping narratives remain recoverable through Git at
`77c3071`; no archive tree or history rewrite was created. The older repository-checkpoint,
correction-draft and feature-architecture branch tips were reachable from both main and the feature
branch during housekeeping, with no open PRs/unique work; recheck before any separate deletion approval.
The feature branch is not merged into main. A stale detached worktree registration was left alone.
No branch deletion, PR, merge, runtime/AI configuration or live data operation is part of consolidation.
