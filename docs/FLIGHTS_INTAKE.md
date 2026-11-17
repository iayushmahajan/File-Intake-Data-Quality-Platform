# Flights observation intake — Milestone 3

This adds `raha_flights_v1` intake and durable raw observation persistence alongside
legacy transactions. It does not normalize times, group entities, reconcile values,
generate candidates, call AI, review decisions, or evaluate against reference labels.
The [benchmark foundation](FLIGHTS_BENCHMARK.md) remains unchanged.

## Contract and execution

Use `POST /api/v1/flights/uploads` with multipart `file` containing a CSV. The
dedicated endpoint identifies the contract: no column mapping or transaction rules
apply. The header must contain exactly these seven columns in this order:

```text
tuple_id,src,flight,sched_dep_time,act_dep_time,sched_arr_time,act_arr_time
```

`save_upload_file` supplies the existing UUID basename, exclusive file creation,
chunked write, byte limit, and partial-file cleanup. The endpoint hashes the saved
bytes and rejects the exact known reference snapshot before durable acceptance.
`create_job` commits job, execution intent, import configuration and file metrics
together. It retains the original ambiguous-commit acknowledgement behavior.

```text
POST Flights upload → save original + SHA-256 → create_job (HTTP 202)
  → existing dispatcher → existing Celery task → existing claim token/lease
  → process_flights_file → existing _finish fence
  → observation inserts + count + completion in one transaction
  → GET Flights job / paginated observations
```

The worker branches explicitly on `job_kind`. Flights never validate through
transaction `ImportOptions` or `AnalysisResponse`; transactions retain those paths.
`JobAnalysis` is reused only for file size/duration for Flights; it has no Flights
quality score or analytical report. Flights generate no output CSV artifacts.
Existing transaction attempt-directory ownership and cleanup are unchanged.

## API

| Method/path | Behavior |
|---|---|
| `POST /api/v1/flights/uploads` | Multipart `file`; HTTP 202 with existing `UploadResponse`, job ID, saved basename, `status_url`, and matching `Location` |
| `GET /api/v1/flights/jobs/{id}` | Typed identity/status, contract version, original filename/saved basename, SHA-256, size, timestamps, attempts/duration, authoritative observation count/availability, fatal intake issue and error message |
| `GET /api/v1/flights/jobs/{id}/observations` | Typed raw observations, issues, total, page, page size; ordered by logical record position |
| `GET /api/v1/jobs/{id}/download/input` | Existing original-file download, also usable for Flights jobs |

Pagination defaults to page 1 and 25 observations, with page >= 1 and page size
1–100. A page beyond the result returns an empty list and the same total.
Logical record numbers include the header as record 1; quoted multiline values
do not advance the logical record count more than once.

Request errors: missing multipart file/invalid pagination → 422; absent/non-CSV
filename → 400; file limit → 413; exact blocked hash → 422 with structured detail
(`code`, `field`, `row_number`, `message`). Rejected pre-acceptance input is removed
and no job is created. CSV schema/data checks happen asynchronously after 202.

Unknown job → 404. Wrong-kind job → 409. Pending/queued/processing/failed Flights
observation retrieval → 409. Status retrieval remains available for those jobs,
with observation count 0 until successful publication; active processed_at is null.

Existing `/api/v1/jobs` listing/detail, record queries, corrections and aggregate AI
remain transaction-only. Flights use their returned status URL. Original download
is shared. No frontend changes or Flights listing UI were introduced.

## Raw preservation and failures

Original uploaded bytes and SHA-256 are retained. Worker processing reads only its
saved input, verifies the accepted hash, and checks the reference fingerprint again.
Any changed input fails rather than publishing evidence with incorrect provenance.

Every observation stores all seven exact decoded strings: opaque tuple ID, source,
flight and four time values. There is no trimming, case folding, timestamp parsing,
missing-marker replacement or transaction duplicate-fingerprint rejection. Blank
and unusual time strings, quotes, embedded delimiters, CRLF/newline content and
non-ASCII UTF-8 survive decoding and JSON retrieval. UTF-8 BOM is accepted and
removed only from header decoding; original file bytes remain unchanged.

Duplicate or blank/whitespace-only tuple IDs, wrong headers/order/width, malformed
CSV, invalid UTF-8, and empty datasets fail the entire import. The first fatal
structured diagnostic is saved in JobImport.issues; original bytes remain available.
No authoritative observations or partial count are committed on these failures.

Tuple IDs are limited to 1024 UTF-8 bytes to keep the composite PostgreSQL index
key bounded. NUL-containing cells cannot be represented by PostgreSQL text and
fail explicitly. The standard-library CSV parser's field-size limit also applies;
these limitations never silently truncate a value. File-size defaults are unchanged.

Blank source/flight values are preserved with per-observation `blank_identity`
issues. Unexpected benchmark flight shapes yield `flight_shape`; source surrounding
whitespace/control characters yield `source_shape`. Source identifiers otherwise
remain opaque: no web-domain registry or reliability judgment is imposed. These
issues do not reject a structurally valid import. Repeated source/flight claims
with distinct tuple IDs are retained, without voting or deduplication.

Only `_finish` inserts observations after its conditional token/lease check. The
inserts (batches of 500), job count and completion share one transaction. A failed
later batch rolls everything back; duplicate/stale deliveries cannot rewrite a
completed snapshot. Existing dispatcher recovery and bounded retries apply.
Ambiguous commit acknowledgements retain existing safeguards. There is no edit,
delete, correction or export API for Flights observations. Immutability is enforced
by application ownership and publication semantics, not a database permission
barrier against direct operator SQL. Future derived state must remain separate.

## Additive migration 0004 — not applied to development state

| Addition | Compatibility/constraint |
|---|---|
| processing_jobs.job_kind | NOT NULL; persistent server default `transactions` classifies existing rows and old-style inserts; new Flights jobs explicitly use `raha_flights_v1` |
| processing_jobs.input_sha256 | Nullable; historical hashes remain unknown/null, never fabricated |
| job_imports.issues | NOT NULL JSON; existing rows default to `[]`; bounded first fatal diagnostic for Flights |
| flight_observations | New table; FK to processing_jobs.id, composite PK `(job_id, tuple_id)`, unique `(job_id, row_number)`, check `row_number >= 2`, non-null raw string columns and issue JSON |

Contract version 1 is persisted in the existing JobImport.options snapshot, with
the contract identifier stored once in job_kind. Job ID is the dataset snapshot;
no separate dataset subsystem is added. The position uniqueness constraint also
provides an index for ordered per-job pagination. No future reconciliation tables
or speculative flight/source indexes are created.

Migration 0004 assumes earlier migrations have completed. It checks for preexisting
job columns to preserve the existing adoption test/path; no legacy records/files
are reprocessed, reclassified as Flights, deleted or moved. Old columns and JSON
contracts retain their meanings. No cascade deletion is introduced.

Downgrade raises an error, matching existing retention policy. Before applying to
development PostgreSQL: explicitly approve the rollout, verify database/volume
identity and current migration revision, back up database and associated files,
and confirm a restore plan. Coordinate API/worker versions around the schema
change. Normal API startup automatically upgrades and must not be used as an
unreviewed migration command. No development migration or Docker operation ran
during this milestone. Live PostgreSQL behavior remains unverified.
Accept Flights uploads only after the API and every worker use the new version;
older workers do not implement the Flights branch.

## Reference isolation

Only the published SHA-256 fingerprint is in runtime code. No runtime reference
path, manifest loader, offline inspector import, label fixture or storage mount
was added. Tests use synthetic observations only and need no benchmark files.
The hash gate prevents accidental ingestion of the exact pinned reference bytes;
it cannot detect edited or reserialized reference data. Do not supply those files
to any operational workflow.

## Verification

The existing backend conftest sets temporary SQLite/files, memory broker and empty
AI key before importing application modules. TestClient lifespan migrations operate
only on that disposable state. The added migration constraint test separately uses
a temporary SQLite database with foreign keys enabled. One old migration fixture
now inserts historical columns explicitly rather than using the expanded ORM
against revision 0001; its preservation assertions are unchanged.

```bash
PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests/test_flights_intake.py -q
PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests -q
python3 -B -m unittest discover -s scripts -p test_flights_benchmark.py -q
git diff --check
```

Observed results: 26 focused Flights tests, 149 full backend tests, and 13 benchmark
foundation tests passed. The sandbox stalled in TestClient's thread/event-loop
bridge; bounded backend runs outside that sandbox passed using the same isolated
fixtures. No Redis/PostgreSQL/Docker integration, normal application launch, real
benchmark ingestion, or provider request was performed.
