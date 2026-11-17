# Reconcile Workbench — implementation and operational handoff

The twelve planned milestones are implemented at code/test level, subject to the actual
verification results below. This is a narrow Flights workflow, not a generic repair engine.
No live deployment, production readiness, authentic benchmark performance or aviation truth
is asserted. Git remains on `feat/reconciliation-workbench`; no automatic commits/pushes.

## Engineering walkthrough

| Responsibility | Actual owning path / entry |
|---|---|
| Secure Flights CSV upload | `backend/app/intake/flights_routes.py::upload_flights`, existing `utils/file_io.py::save_upload_file` |
| Durable acceptance | `backend/app/jobs/service.py::create_job`; job kind and input hash retain provenance |
| Dispatch/recovery | `backend/app/services/dispatch.py::dispatch_once`, `recover_expired`; `app/dispatcher.py` loop, existing Celery task transport |
| Claimed execution | `backend/app/services/job_processing.py::claim_job`, `process_job`, `_finish`; attempt tokens/leases fence publication |
| Raw observation parsing | `backend/app/intake/flights.py::process_flights_file`; immutable `FlightObservation` rows published with completed job |
| Grouping/normalization | `backend/app/reconciliation/observations.py::load_grouped_flights`, `grouping.py::group_flights`, `normalization.py::normalize_time` |
| Deterministic evidence | `backend/app/reconciliation/evidence.py::investigate_field`; `routes.py` list/detail projections |
| Optional AI | `investigations.py::investigate`, `reserve`, `present`; `ai.py::prepare_evidence`, `validate_recommendation`; explicit request only |
| Human mutations | `review.py::submit_review`, `validate_action`, `effective_review`; append-only `FlightReviewDecision` and monotonic revision |
| Frozen exports | `reviewed_exports.py::capture_snapshot`, `create_export`, `write_artifacts`, `artifact_bytes`; revalidate under shared review publication gate |
| Offline evaluation | `scripts/evaluate_flights.py::evaluate`; file-only checks before explicit reference read |
| SPA composition | `frontend/src/routes.tsx`, `components/layout/ApplicationLayout.tsx`; Home, Datasets, Investigate, History and protected legacy route |
| History/export UI | `features/history/HistoryPage.tsx`, `ExportPanel.tsx`, `contracts.ts`; centralized API errors, scoped requests and same-ID uncertain retries |

Flights job history adds only `GET /api/v1/flights/jobs`: page 1+, page size 1–100 (default 15),
optional existing job-status enum, Flights-only count/query and deterministic creation/ID descending
order. Two bounded queries use outer joins for import/metrics metadata, not observation loads.
Missing import metadata is displayed as unknown rather than classifying historical transactions
as Flights. It is read-only and needs no schema migration. Existing legacy history still filters
transactions. Field history reuses existing review/history endpoints; no new audit-log framework.

History loads 15 jobs, 5 exports and 15 field choices per page. Only the selected field's current
review/history is fetched. Current, stale and superseded events are labeled separately. Existing
exports remain downloadable even if the current snapshot cannot be generated. Creating a new
snapshot requires acknowledgement; POST uses the server digest and UUID, uncertain failures
retain both, and 409 refreshes without automatic resubmission. Reads and downloads time out
at 15 seconds; writes at 45. Browser abort does not cancel accepted backend work. Unsubmitted
local state is scoped to the selected view; returning retrieves persisted server state.

## Migration and storage gate — not executed

Source migration chain is `0001 → 0002 → 0003 → 0004 → 0005 → 0006` (head `0006`).
`main.py::lifespan` invokes `core/db.py::migrate_database` and `alembic upgrade head`.
0004 adds job-kind default `transactions`, input hash, import issues and raw observation table;
0005 adds claimed non-authoritative investigation history, attempt/slot constraints and partial
indexes; 0006 adds review events and immutable export metadata with request/revision constraints.
No subsequent source revision exists. Their destructive downgrades are disabled; rollback is a
reviewed coordinated restore, not a casual downgrade. M12 adds no migration.

Existing Compose source defines PostgreSQL 16, Redis 7, API, worker and dispatcher. Database
and Redis use project-scoped `postgres_data` and `redis_data`; API/worker bind `./backend/data`
to `/app/data`. API 8000 and Redis 6379 are loopback-bound. Database/user `intake`, queue
`csv-processing`, worker task identifiers and dispatcher heartbeat are operational names, not
public branding. The documented launcher project name `file-intake-processing-service` is
source guidance, **not a verified runtime project/volume identity**. No Docker commands were
used in M12. Keep existing infrastructure identities until a separately reviewed requirement
justifies isolation. A new Compose name does not automatically reuse existing volumes.

Future rollout sequence (requires explicit authorization before mutations):

1. Read-only identify actual Compose project, container labels, mounts, port ownership and
   exact database/Redis volume names. Confirm target database identity, not just a URL string.
2. Read actual `alembic_version`; inventory legacy and Flights row aggregates, input files,
   outputs and frozen-artifact directories without exposing private rows/secrets.
3. Coordinate quiescence of intake/review/export writes and workers; record a consistent
   database dump plus complete application file storage and required configuration ownership.
   A database-only backup is insufficient for retained inputs and frozen artifacts.
4. Restore into an explicitly disposable PostgreSQL environment with unique ports, project
   labels, volumes and DATA_DIR. Verify restored row/file hashes and legacy accessibility.
5. Test forward migration from that restored revision to 0006. Confirm legacy default kinds,
   constraints, partial indexes, all raw strings, existing AI/history and artifacts survive.
6. Test PostgreSQL AI claim-slot uniqueness and interrupted leases, concurrent review revisions,
   exact retries and review/export snapshot races. SQLite tests do not establish these semantics.
7. In the same isolated environment verify Redis/Celery acceptance, duplicate deliveries,
   worker fencing, dispatcher recovery, restart and ambiguous-commit behavior.
8. Run a browser journey using a synthetic CSV and fake provider against that backend; verify
   persisted raw values, decisions and all downloaded artifact hashes after process restart.
9. Obtain approval for the intended real environment, backup/restore point and maintenance
   window. Only then migrate/start services and verify revision, preservation and recovery.
10. Retain tested backups and a restore procedure until post-rollout acceptance is complete.

No such environment was authorized/verified during this milestone. Normal development startup,
Compose operations, existing database migrations and volume changes remain unexecuted.

## Controlled real-provider gate — not executed

Supply local secrets only through environment: `OPENAI_API_KEY`, a verified compatible
`OPENAI_BASE_URL`, and `OPENAI_MODEL`; do not publish credentials. Obtain explicit approval for
one synthetic eligible field and its possible provider charge. Keep the endpoint private/local;
there is no production authentication. Inspect the complete deterministic evidence and budgets
before requesting. Existing bounds: at most 32 claims / 8 candidates / 32,000 input bytes,
2,048 output tokens, 30-second total request deadline, zero SDK retries, two active claims,
three reserved attempts per scope/configuration. Model pricing must be checked at approval time;
no exact cost is promised. Verify schema/citations, reported usage, provider failure, persisted
freshness and unchanged observations. A returned proposal is still unapproved until human review.
Do not approve a repair just to make a smoke test pass. Fake-provider tests are not live compatibility.

## Offline benchmark gate — not executed on authentic frozen results

Use only the manifest-pinned observed bytes after verifying their hash. Preserve the external
reference root outside runtime storage/mounts. Freeze proposals/reviews before any reference
read. Save the export metadata response from `GET .../exports/{export_id}` and unchanged reviewed,
exceptions and provenance artifacts. Follow `FLIGHTS_EVALUATION.md` with explicit reference path,
external report path and integrity checks. Do not expose labels through API/UI or tune against
reference answers. Synthetic evaluation tests are explicitly demonstrations, not measured product
performance. Underlying third-party provenance/redistribution/demo rights remain unresolved.

## Branding / external synchronization checklist — no renames executed

UI, browser title/favicon and OpenAPI metadata use working brand **Reconcile Workbench** and
descriptive **AI-Assisted Data Reconciliation & Quality Workbench**. Legacy UI is labeled
**Legacy transaction workspace**. Old sample/development docs retain transaction-specific names
as historical capability. Existing operational identifiers remain intact.

Separately approve each applicable external step:

- Confirm public brand and proposed repository slug `ai-data-reconciliation-workbench`.
- Review GitHub rename redirects, local remote URL updates and README/clone URLs; do not
  assume the local repository basename must change with a remote rename.
- Inventory CI, deployment repository references, badges, webhooks, registry/image tags and
  external hosting settings; update together after review. No remote/deployment state was inspected.
- Keep Compose project and volumes by default; if isolation is justified, review exact storage,
  backup/restore, port allocation and migration/cutover before creating a new namespace.
- Coordinate database/Redis names, queue names, task routing and healthchecks only if a real
  operational requirement exists. Never perform a broad string replacement of `intake`.
- Review environment examples and secrets outside Git without printing their values.
- Confirm SPA fallback, allowed frontend origins and a production security/access-control plan
  before exposure. Working single-operator behavior does not establish deployment security.

## Verification record

Final commands/results are recorded in the Milestone 12 completion report. Frontend unit tests,
production build and the isolated browser harness use synthetic APIs; backend pytest fixtures
configure temporary SQLite and files plus memory broker before imports. Offline tests use
synthetic references. PostgreSQL/Redis/Celery runtime, real provider, authentic benchmark results,
production hosting and coordinated backup/restore remain outstanding. A restricted-environment
backend test timeout must not be reported as a passing suite; only a completed rerun counts.

Completed verification on this working tree: backend **294 passed** in 174.96 seconds using
`timeout 180s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests -vv -o faulthandler_timeout=20`;
new history/schema subset **6 passed**; frontend **139 passed**; production build passed;
benchmark/evaluator standard-library suite **24 passed**; isolated Chromium harness **46 checks
passed**, including the synthetic upload → investigation → review → History → freeze → three
download journey. `git diff --check` passed. The initial restricted backend run timed out at
TestClient after eight schema checks, an intermediate rerun ended with signal 143, and the
completed verbose run is the passing regression evidence. No tests were weakened to bypass
those interruptions. Build warning: existing stale Browserslist database. No dependency update
was performed. All migration tests used disposable SQLite; PostgreSQL remains unverified.

Acceptance classification: parsing/durable job behavior, normalization/evidence, fake-provider
AI, review/revisions/history, frozen artifacts, offline synthetic evaluation and the API/UI
journey are **verified in isolated tests only**. Styling/responsiveness and frontend production
build are **verified working** for the tested Chromium/viewports/build. Real PostgreSQL/Redis/
Celery, real-provider compatibility and deployment configuration are **implemented but
unverified**. Authentic frozen benchmark evaluation and approved backup/restore/cutover are
**incomplete operational verification**, not fabricated successful runs. External renames and
production deployment remain unexecuted and require separate approval. No known failing code
tests remain in the completed verification; this is not a promise of defect-free deployment.
