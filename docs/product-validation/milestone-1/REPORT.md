# Product validation — Milestone 1

2026-11-16 · **Passed at persisted in-process API / SQLite level.** Browser persistence, live PostgreSQL concurrency and real Redis/Celery transport remain unverified by this run. No AI or offline benchmark evaluation was executed.

## Isolation established before writes

An existing test database was available: `/tmp/file-intake-tests-ayazlfd0/tests.db`. It already contained the complete `0006` schema and zero application rows. This is a reused test resource, **not** a newly created database or a copy of development data.

Read-only inspection verified owner UID 1000 matched the operator; its parent directory was private `0700`; neither path was a symlink; the database had one hard link, was writable and had no open-file owners. It overlapped none of the protected project's mounts. Two other leftover test directories were inspected but not used; one had an incomplete schema and journal file. Unrelated projects/test containers were not adopted or operated.

The selected storage directory was `/tmp/file-intake-tests-ayazlfd0/product-validation-m1`, outside repository application storage and Docker mounts. Connections used `sqlite:///file:/tmp/file-intake-tests-ayazlfd0/tests.db?mode=rw&uri=true`: SQLite refused database creation. The runner asserted the original database inode and schema remained unchanged. Broker settings were `memory://`, queue `product-validation-m1`; no external worker, Redis connection or dispatcher was started.

The runner uses the real `app.main.app` routes through in-process `TestClient`, without entering its lifespan context. Migration functions, provider execution and socket connections were replaced with fail-fast **safety guards**, not simulated API responses. A SQL listener rejected CREATE/DROP/ALTER/DELETE/REPLACE/ATTACH/DETACH/VACUUM and observation updates. Successful SQL was limited to INSERT, SELECT, UPDATE and BEGIN. API handlers, processing, normalization, evidence, review and exports were not mocked.

This avoided the existing pytest autouse fixture: `backend/tests/conftest.py` creates a new temporary database, drops tables and runs migrations. It was inspected but deliberately not executed under this milestone's restrictions. `frontend/scripts/run-e2e.mjs` also creates/removes Redis resources and occupies API port 8011; it was not run.

Evidence: [isolation.json](evidence/isolation.json), [runner](verify_workflow.py).

## Protected environment baseline and preservation

Before and after validation:

| Protected measurement | Before | After |
|---|---:|---:|
| Database identity | reconcile_workbench | reconcile_workbench |
| Migration revision | 0006 | 0006 |
| Completed Flights imports | 5 | 5 |
| Source observations | 11,880 | 11,880 |
| AI investigations | 0 | 0 |
| Review events | 0 | 0 |
| Frozen exports | 0 | 0 |

Ordered job fingerprint: `8ea0fc0887ea82c51c139cb65b752f7a`; ordered observation fingerprint: `070030e0d35ae58bb262b23b9c7464e1`. Both matched exactly. These repeatable MD5 fingerprints detect accidental changes; they are not an authenticity/signature claim. The complete Flights job-list response was byte-identical. Dedicated container IDs, start timestamps, mounts and network metadata matched exactly.

Protected volumes remained `reconcile-workbench_postgres_data`, `reconcile-workbench_redis_data`, and `reconcile-workbench_app_data`. No operation started, stopped, recreated or migrated those services. The original `file-intake-processing-service` containers remained outside the validation workflow; its database and files were not opened or modified. No raw benchmark CSV was acquired or uploaded into either protected project.

Evidence: [protected-baseline.json](evidence/protected-baseline.json).

## Synthetic cases and provenance

The operator-authored fixture uses the existing seven-column `raha_flights_v1` contract. It contains seven fictional source records and three fictional flights; it is not an extract of Raha, a reference dataset or a performance benchmark. Fixture SHA-256: `bafbefd3e1dbd35096517893345a1cf9c54f71194e46846229ed8fda2c536713`.

| Case | Constructed input / expected behavior | Actual result |
|---|---|---|
| A: ZZ-100-AAA-BBB, actual departure | 17:08 from one source; 17:09 repeated twice by a different single source. Retain conflict and count reports separately from sources. | Two candidates: 17:08 → 1 source / 1 report; 17:09 → 1 source / 2 reports. Confirmed conflict; baseline abstained. No value approved. |
| B: ZZ-200-CCC-DDD, actual arrival | Empty string and `Not Available`; no justified clock. | Missing and placeholder findings stayed distinct; no candidate. Explicit unresolved review persisted with rationale and no effective value. |
| C: ZZ-300-EEE-FFF, scheduled departure | `9:00 AM` and `09:00 a.m.` support the same clock. Explicit human selection with documented basis. | One 09:00 candidate and formatting variation, no semantic conflict. Human `override` selected that existing candidate. Source references were retained. |

Case C demonstrates source-supported judgment against a deliberately constructed fixture, **not independent verification of historical truth**. No majority vote or clean-reference answer was used as authority.

Job ID 1 in this report belongs exclusively to the isolated SQLite database. The existing browser frontend continues to use the separate protected PostgreSQL environment.

Evidence: [synthetic-observations.csv](evidence/synthetic-observations.csv), case responses in [results.json](evidence/results.json).

## Actual workflow and expected versus actual checks

1. `POST /api/v1/flights/uploads` returned **202** and a durable pending job, isolated job ID **1**. `process_job(1)` used the existing conditional-claim/publication path and returned completed. Its duplicate invocation returned ignored; exactly seven observations remained. This invokes the real worker-owned processing function directly, not Celery transport.
2. Job detail verified completed status, exact file bytes/hash and seven observations. The all-fields endpoint returned **12** field cases. Selected evidence exposed the actual claims and support counts above.
3. Case C `POST .../review` used the server digest, expected revision 0, supported candidate ID, reviewer `Synthetic validation reviewer`, rationale and UUID request ID. It returned **200**, action override, revision **1**, canonical **09:00** and the candidate's genuine observation references.
4. An exact retry returned the identical event. Conflicting reuse of that request ID, a stale revision and a stale evidence digest each returned **409**, without creating another event.
5. Case C was explicitly re-reviewed at revision **2**, preserving revision 1 and its original rationale. Case B received an unresolved event at revision **1**, with null candidate/resolution and an explanation of insufficient evidence.
6. Closing the client, disposing the pool and making requests through a new client retrieved the persisted states. History pages of size one returned C revisions **1 and 2** in order with their actual event IDs, attribution and rationales.
7. A snapshot read preceded frozen export creation. Exact export retries returned the same export; conflicting request reuse returned **409**. Artifact contents, not just response codes, were checked below.
8. After freezing, Case B received a second unresolved event. Its current snapshot digest changed. A fresh export request with the old digest returned **409**; retrying the original export request still returned the original frozen export. All earlier events and artifact bytes remained intact.
9. A separate read-only Python process verified all four event IDs/revisions/actions/rationales/request IDs on disk, all seven exact original rows and revision 0006, after the API process had exited.

Outcome: **36 real API checks passed**, including expected 409 conflict responses. Four append-only events exist: C override revisions 1/2 and B unresolved revisions 1/2. AI investigations remain zero. No provider was needed for these decisions.

Important owners: `intake/flights_routes.py::upload_flights`; `services/job_processing.py::process_job` / `_finish`; `reconciliation/review.py::submit_review`; `reviewed_exports.py::capture_snapshot`, `create_export`, `render_snapshot`; `review_routes.py` exposes review/history/export endpoints. Source modules were not changed.

## Frozen artifact verification

Export ID: `399e6a0d689448ecb9a6313441cbf965`.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| [reviewed.csv](evidence/reviewed.csv) | 763 | `4042cd8c79b049e10668a9a3beae823ab3eb983f0bc4fb7f57a22bd5bbb61a75` |
| [exceptions.csv](evidence/exceptions.csv) | 2,068 | `dd72e3737a6bc351f75b277972dbdb2fdcd50ebce2c3892ba4c9af854062f349` |
| [provenance.json](evidence/provenance.json) | 13,478 | `fc077c86b9bcb93d1ab7d54ba921b72c8852e5ac86f7ff0cbecdbb0fe2ef19a3` |

- Reviewed CSV contains three flight rows and **one** approved field: Case C 09:00, status overridden, its revision-2 event ID. The other **11** fields are empty as authoritative values, including undisputed fields without human approval.
- Exceptions contains **11** field rows: ten unreviewed and one explicitly unresolved. Case A's conflicting values were not silently exported as approved.
- Provenance captures all 12 field identities, original observation mappings, evidence policies/digests, decision references and the frozen B revision 1 / C revision 2 state. Case C maps to `pv-c-1` and `pv-c-2`; manual provenance was not invented.
- Each download's byte length/hash matched [export-metadata.json](evidence/export-metadata.json). Pure re-rendering with the frozen snapshot, export ID and timestamp reproduced **all three artifacts byte-for-byte**. This does not claim separately generated exports with new identities/timestamps are identical.
- After the later B review, downloads and metadata for this export stayed byte-identical. Only one export metadata row existed; retries did not produce duplicate snapshots.

## Original evidence immutability

The complete ordered persisted-observation SHA-256 was `79059d04649504d0c1cfe1d614360ef7adf3f882aeebc7fd3b1fde887f83b2c2` before and after reviews/exports. All observation models compared equal; an independent read-only process also compared all seven raw rows to the fixture. Uploaded bytes and input SHA-256 remained unchanged. The import's full status response was unchanged after review/export activity. The test database's schema was unchanged, and the SQL guard prohibited observation updates and any deletion statement.

Evidence: [independent-readback.json](evidence/independent-readback.json), [results.json](evidence/results.json). The isolated database and generated application storage were retained; no cleanup/reset/deletion was performed.

## Commands, failures and limits

Successful bounded invocation from the repository root:

```bash
timeout 60s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -B \
  docs/product-validation/milestone-1/verify_workflow.py \
  --database /tmp/file-intake-tests-ayazlfd0/tests.db \
  --evidence-dir docs/product-validation/milestone-1/evidence
```

**Do not rerun this command as cleanup or against another application database.** The runner refuses a nonempty database or existing evidence/storage output. It is a record of this controlled run, not a new benchmark framework or CI fixture. It requires a separately verified existing private empty test database at 0006; it never creates or migrates one.

The initial restricted-sandbox invocation stalled before its first request created any records. It was stopped; a read-only count confirmed the test database was still empty. The retry outside that sandbox used a 60-second command limit, 45-second traceback watchdog and all isolation guards, and passed in about one second. No application defect or contract bypass was needed. Independent readback and protected before/after comparisons passed. `git diff --check` passed. No full pytest suite was run because its normal fixtures create/drop/migrate databases; no frontend rebuild was needed because application code was unchanged.

Browser-level persistence is **not verified**: TestClient is in-process and does not listen on a browser URL. The existing frontend points to protected API port 8011; no alternate writable HTTP server/frontend or Docker environment was created to change that. No mocked browser screenshots are offered as proof. Real PostgreSQL locking, queue transport, recovery under interruption and paid-provider compatibility remain separate gaps. Reference evaluation tooling was inspected but not executed; no `clean.csv` or reference labels were opened.

## Read-only Git checkpoint assessment

Baseline branch `feat/reconciliation-workbench`, HEAD `6e89b94ab4bd40926b46c893f45cf8552351e860`: **27 tracked modified files, 210 untracked files, no staged changes**. Existing changes cover intended Flights contracts/persistence, migrations 0004–0006, deterministic evidence, AI/review/exports/evaluation, frontend routes/UX/assets/tests, dedicated Compose/scripts and handoff/benchmark documentation. They remain uncommitted; local state, not the remote, is the evidence source.

Local-only/generated items to keep out of a future code checkpoint:

- `.env`, `.env.reconcile.local`, `backend/.env`, `frontend/.env`: all exist, are ignored and have mode **0600**. Values were not printed or copied. Only reviewed example files belong in source control.
- Virtual environments, `node_modules`, `frontend/dist`, TypeScript build state, Playwright reports/test outputs, local databases and application uploads/exports are ignored. Input/output directory placeholders are intentionally retained; ignore rules protect their contents.
- `dirty.csv` / `clean.csv` are globally excluded by existing rules; do not force-add them or the reused `/tmp` test database/storage.
- The untracked `docs/ui-review/live-workflow.zip` is a **5,597,627-byte generated archive** of 34 Markdown/PNG entries, duplicating review material. Recommend excluding it from a code checkpoint rather than deleting it automatically.
- The repository has **115 documentation images, approximately 17.96 MB**. Curate screenshot galleries separately; inspect visible data and benchmark redistribution/demo rights before publication. Preserve required frontend brand assets in the application checkpoint.
- New evidence here is approximately 47 KB plus this report/runner, uses fictional values only and may be retained as explicitly labeled validation evidence. It is not benchmark performance data.

A limited filename/content scan found no private-key/provider-token patterns in candidate text files. It skipped binary/large content and did not inspect ignored secret values; this is **not a comprehensive secret audit**. Archive member names contained no `.env`, dirty or clean CSV files; internal image/content review remains a human publication check. See [git-assessment.json](evidence/git-assessment.json).

Recommended checkpoint: review an explicit file manifest and both tracked diffs and untracked source; approve one coherent application/tests/contracts/dependency-lock/configuration/documentation baseline so no half-working dependency slice is committed. Review optional screenshots/archive separately. Keep secrets, runtime data, build output and benchmark bytes excluded. Stage/commit only after explicit approval; avoid a blanket add. Final Git state remains 27 tracked modified files and now 222 untracked files: the only additions are this report, its runner and ten small evidence files (12 files total). Fingerprints of every pre-existing repository file matched the initial baseline; no existing file was changed or lost. Nothing was staged, committed, pushed, switched, reset, stashed or discarded in this run.

## Next small validation task: genuine AI, separately approved

Use the isolated existing test import's Case A for one explicitly approved provider request. Record its current evidence digest, tied distinct-source baseline, authorized candidates, model/configuration, actual usage/latency and safe result category. Demonstrate explanation and uncertainty with valid citations, or a justified abstention; do not expect an authoritative answer from conflicting reports. Keep suggestion separate from human approval. A valid schema/reference set does not prove the prose is faithful or useful.

Prerequisites: approve provider/model, privacy handling and spending cap; configure credentials only for an isolated process, verify request-parameter compatibility, keep it private and permit no automatic retries. No keys belong in this report/repository. The current evidence budget is 32 claims, 8 candidates and 32,000 input bytes, with 2,048 completion tokens and bounded deadlines; use one case/one request initially. No clean reference or comparison report enters the operational process or prompt.

One smoke test can show actual provider behavior and groundedness, not measurable accuracy uplift. A later preselected flight-separated comparison should assess valid grounded suggestions, abstention/failure rates, harmful suggestions, actual cost and reviewer effort against the same deterministic baseline. The existing offline evaluator scores frozen reviewed exports; it does not directly score AI-versus-baseline suggestions. Any reference-based scoring must occur only after outputs are frozen in the separate offline evaluation boundary, with explicit units/exclusions. No new provider, prompt, endpoint, instrumentation or evaluation implementation was added here.

**Stop:** isolated persisted workflow verified; no AI experiment, browser write run, protected-data write or next milestone was executed.
