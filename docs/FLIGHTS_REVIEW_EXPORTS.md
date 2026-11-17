# Human review and frozen Flights exports — Milestone 7

This feature records explicit local reviewer assertions. It does not determine ground truth,
change observations, call an AI provider, evaluate benchmark accuracy, or implement authentication.
Human review works with no AI configuration or reference storage.

## Review contract

Policy: `flight_human_review_v1`. Scope remains `(job_id, raw flight, field)` and its existing
stable discrepancy ID. The four time fields and all normalization/evidence policies are unchanged.

Under `/api/v1/flights/jobs/{job_id}/discrepancies/{discrepancy_id}`:

| Operation | Result |
|---|---|
| `GET /review` | Effective state, latest revision, current evidence digest, latest event, stale flag and effective resolution |
| `POST /review` | Appends one decision event, or returns the existing exact retry |
| `GET /review/history?page=1&page_size=25` | Chronological events including superseded decisions; page size 1–100 |

POST requires `action`, `expected_evidence_digest`, `expected_revision`, `request_id`, and
`reviewer_label`. Request IDs are 8–80 ASCII letters/digits/underscore/hyphen. Unknown fields
and wrong types are rejected. A reviewer label is self-declared local attribution, **not an
authenticated identity**; current review returns `reviewer_identity_verified: false`.

- **accept**: requires `investigation_id` only, with no client-selected value. The investigation
  must be a current `proposed` result in this job/field, with matching digest/configuration.
  The stored strict AI response and all candidate/citation references are validated again.
- **override**: requires a rationale and exactly one `candidate_id` or `manual_value`. Candidate
  selection works without AI. An optional investigation reference must identify a current
  valid proposal; omit it when reviewing without a proposal, including AI abstention/failure.
- **reject**: requires a current valid proposal's `investigation_id` and rationale. Its candidate
  is retained as rejected provenance; no effective value is created.
- **unresolved**: optional rationale, no candidate, manual value or investigation selection.

Reviewer label limit: 80 characters; rationale: 1,000 characters; manual input: 160 characters.
A manual clock is validated by the existing `normalize_time()` v1 grammar. Only `parsed`
results are accepted: explicit AM/PM, supported 24-hour forms or noon. Ambiguous bare 1–12
clocks, unsupported annotations, placeholders and invalid values are refused. The exact
entered text is retained alongside canonical clock, precision and qualifiers. It is labeled
`human_assertion` with **empty** source-support lists. Candidate choices retain actual observed
support IDs and are labeled `observed_candidate`. No observation provenance is fabricated.

Effective states are unreviewed, accepted, overridden, rejected and unresolved. A later action
supersedes the prior effective action, including reopening an approved field. All events remain.
A changed evidence digest makes the old event stale: current state is unreviewed, `stale: true`,
and effective resolution is null. Re-review uses the new digest and the latest stored revision.
A subsequent provider outage/configuration change does not revoke an already explicit human
approval while its source evidence remains current. AI states remain separate, available through
the existing investigation endpoints. Neither AI nor baseline output becomes approval implicitly.

## Revision, idempotency and database guarantees

New review writes reconstruct deterministic evidence from immutable persisted observations.
Revisions start at 1; clients use expected revision 0 for an unreviewed field. Unique
`(job_id, discrepancy_id, revision)` and globally unique review request IDs prevent lost
updates. Request fingerprints cover scope and the complete parsed payload. Exact retries
return the original event even after later decisions; changed-payload reuse is 409.

Normal review paths only INSERT events; they never UPDATE/DELETE earlier events or modify
source/job/import rows. There is no separate mutable current-state table. Current state is
the greatest revision, with evidence freshness checked independently.

Review insertions and final export publication share a short job-row gate: PostgreSQL
`SELECT ... FOR UPDATE`, or SQLite `BEGIN IMMEDIATE`. The existing job row is locked, never
modified. Expected revisions are still checked; database uniqueness remains the final guard.
This gate prevents a review from slipping between export revalidation and metadata commit.
File generation and provider calls do not run while holding it. PostgreSQL locking behavior
has not been exercised against a live server; threaded disposable SQLite tests cover the gate.

Errors: 404 unknown job/scope; 409 stale evidence/revision, conflicting request key, invalid or
stale investigation, incompatible job/version, bounds or corrupt stored evidence/review; 422
invalid request/candidate/manual clock; 503 safe database diagnostics. A failed transaction
cannot publish a partially inserted current decision. An ambiguous acknowledgement is retried
using the same request ID. Historical review GET still requires projectable current scope;
corrupt/unsupported source snapshots return 409 rather than pretending to have current evidence.

## Frozen export API

Under `/api/v1/flights/jobs/{job_id}/exports`:

| Operation | Result |
|---|---|
| `GET /snapshot` | Current deterministic snapshot digest, field count and ungroupable count |
| `POST` | Requires `expected_snapshot_digest` and `request_id`; creates three complete artifacts |
| `GET ?page=1&page_size=25` | Bounded newest-first export history, page size 1–100 |
| `GET /{export_id}` | Frozen metadata and hashes/sizes |
| `GET /{export_id}/download/{artifact}` | Allowlisted `reviewed`, `exceptions`, or `provenance` artifact |

The snapshot digest covers input SHA-256, contract/policies, all field evidence digests,
effective decision IDs/revisions/metadata/resolutions, source-observation mapping, ungroupable
observations and any unmapped historical decisions. Generation time/export UUID are excluded
from this content identity. A fixed snapshot, export UUID and generation time render identical
bytes; a new export receives a new UUID/time. Exact request retries return the original snapshot,
even after newer decisions. Conflicting reuse of an export request ID is 409.

All latest decisions are captured in **one SQL statement**, so fields cannot mix revisions
from independent per-field reads. Sources are immutable through application paths. After
complete file generation, the snapshot is rebuilt under the shared publication gate. Changes
are rejected with 409 and owned unpublished artifacts are removed. Revalidation and metadata
commit share that transaction; a waiting review becomes a later event after publication.

## Exact artifact contracts

**reviewed.csv** starts with `job_id,export_id,flight`. For each field in contract order
(`sched_dep_time,act_dep_time,sched_arr_time,act_arr_time`) append these four columns:

```text
{field},{field}_status,{field}_decision_id,{field}_revision
```

One row per groupable flight. Only current **accepted/overridden** decisions populate the time
column, using a validated canonical 24-hour clock and preserved precision. Canonical output
is already interpreted, e.g. `09:22` means the canonical 24-hour value; do not reparse it as an
ambiguous raw source clock. Provenance retains precision/qualifiers. Rejected, unresolved,
unreviewed and stale fields have empty values and explicit corresponding statuses. Even
conflict-free observed agreement stays unreviewed/empty until human approval. No provisional
majority or AI value is silently substituted. Revision is 0 and decision ID empty when absent.

**exceptions.csv** columns, in order:

```text
job_id,export_id,flight,field,discrepancy_id,review_status,reason,decision_id,revision,tuple_id,src,row_number
```

One exception for every unapproved field (`no_human_approved_value` or `stale_review`), plus
one per ungroupable observation, retaining original identity and missing/flagged-flight reason.
Group-level exception tuple/source/position cells are empty; the manifest lists all associated
observations. Ungroupable exceptions have no invented discrepancy/group identity or field.
Their manifest entries explicitly list all four observation-cell fields.

**provenance.json** includes export ID/time, snapshot digest, source input SHA-256 and contract,
normalization/detection/review/export policies, every included field/digest, full effective
human event metadata, canonical resolution and origin/support references, and exact observation
`tuple_id`, `src`, logical position and source-usability mapping. It includes original
ungroupable identity/issues and any unmapped decision events. CSV hashes/sizes are embedded.
The manifest cannot contain its own recursive hash: metadata returned by the API stores all
three artifact hashes/sizes, including the manifest. SHA-256 provides integrity checks, not
a signature or independent proof of data correctness.

Future offline evaluation maps `(job_id, raw flight, field)` to each listed
`(job_id, tuple_id, field)`, never row order. Accepted/overridden values are human assertions
projectable onto those cells; manual assertions carry no invented source support. Rejection,
unresolved, unreviewed, stale and ungroupable entries remain unapproved, not implicit repairs.
AI abstention/failure has no effective export value without an independent human action.
The evaluator, reference loading, equivalence policy and metrics remain Milestone 8 work.

## File safety and bounds

Artifacts live under existing `OUTPUT_DIR/flight-reviewed/{server_uuid}/` with fixed filenames;
clients cannot supply paths. A unique `.pending-{uuid}` directory receives exclusive-create,
UTF-8 files with file flush/fsync. Only complete files are renamed into the UUID namespace,
and only a successful database commit makes them downloadable. Existing destinations are
refused. No file-generation transaction is held open. The final bounded snapshot revalidation
and metadata commit use the short publication gate described above.

Generation failure cleans its owned pending directory. Stale pre-publication generation removes
its owned complete directory. Duplicate export races return the winner and remove only the
loser's unique artifacts. Commit/acknowledgement failures retain complete unique files because
the database may already have committed. Orphans without metadata cannot be downloaded;
interrupted processes can also leave unpublished pending directories. Retention/cleanup requires
review of metadata ownership; no automatic sweeping/deletion framework is introduced.

Downloads use allowlisted labels, UUID validation, root/symlink restrictions, bounded reads and
SHA-256/size verification; missing artifacts are 404, integrity/storage-layout conflicts 409,
oversized generation 413, filesystem/database failures 503. Files are application-immutable,
not OS-WORM or protected against a privileged local filesystem administrator. Serve source
strings as data, not HTML. No secrets/configuration are included in artifacts.

CSV uses standard quoted cells/newlines. Presentation escapes any string beginning with an
apostrophe, formula marker (`=+-@`), whitespace/BOM, or containing control characters by
prefixing one apostrophe. Since original apostrophe prefixes are also escaped, removing exactly
one leading apostrophe reverses this policy. JSON stores exact identities and should drive
evaluation. Stored observations and input files are never presentation-escaped or changed.

The existing 5,000-observation cap, 250 claims per field and 64 candidates per field still apply.
At most 20,000 field scopes are projected; combined artifact size is limited to **32 MiB**.
Excess fails as a whole, with no partial/truncated authoritative output. This is bounded
in-memory/local-disk generation for the narrow benchmark, with no queue/cache/distributed exports.

## Migration and verification

Additive migration `0006` adds only `flight_review_decisions` and `flight_reviewed_exports`.
No old columns/rows/defaults are changed or backfilled. Review revisions/actions/request IDs
and export request IDs have constraints; reviews reference jobs and optional AI investigations,
exports reference jobs. Nullable selection/manual/resolution fields represent unapproved states.
There are no delete cascades. Events/artifacts are retained with their parent job history.

Disposable SQLite tests upgrade from `0005`, preserve legacy jobs, observations and AI history,
and exercise uniqueness/check/foreign-key constraints. No development database was migrated.
Live PostgreSQL/Redis/Celery/provider operation remains unverified. The normal server auto-migrates
at startup: do not launch it against development storage before separate rollout approval.
Back up the database plus original/output storage, verify restoration, and apply `0004`–`0006`
only under an approved rollout plan. Downgrade remains deliberately disabled; rollback requires
a reviewed backup/restore plan with explicit retention of newer review/export history/files.

Tests use synthetic observations, mocked AI and temporary SQLite/files only. New export tests
isolate output directories per case. No reference data, new dependency, frontend change,
provider call, Docker operation or public rebranding is needed by this milestone.
