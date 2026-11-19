# Reconciliation contracts

Deterministic interpretations, source support, AI suggestions and human approvals are distinct.
A detected difference is not proof of an incorrect value; approval records reviewer judgment,
not independently verified historical truth. Original observations are never rewritten by review.

## Flights intake and identity

Contract **`raha_flights_v1`**, version 1, accepts exactly this UTF-8 CSV header/order (optional BOM):

```csv
tuple_id,src,flight,sched_dep_time,act_dep_time,sched_arr_time,act_arr_time
```

`POST /api/v1/flights/uploads` accepts multipart `file`, no mapping/transaction options, saves
original bytes under an exclusive UUID name and hashes them. It returns 202 with job ID,
`Location` and `status_url`; structural validation happens asynchronously. The worker verifies
the input SHA again. Exact known clean-reference bytes are blocked before acceptance and during
processing; this fingerprint cannot identify edited/re-serialized reference data. Never upload it.

Observation identity is `(job_id, opaque tuple_id)`; logical CSV position is separate (header=1,
first observation=2, including quoted multiline records). All seven decoded strings survive
unchanged, including whitespace, empty values, Unicode and markup-like text. No trimming,
case-folding, time parsing, placeholder replacement or deduplication alters raw storage.

Malformed CSV/UTF-8, wrong header/order/row width, empty data, missing/duplicate tuple IDs,
NUL cells or tuple IDs over 1,024 UTF-8 bytes fail the entire import. CSV parser field-size
limits also apply. Only the first fatal structured diagnostic is stored; no partial authoritative
observation index is published. Blank source/flight and unexpected identity shapes remain rows
with issues (`blank_identity`, `source_shape`, `flight_shape`). Repeated reports with distinct
observation IDs remain evidence. Batched observation inserts, count and completion share the
worker's fenced transaction. Immutability is application ownership, not protection from direct SQL.

## Read APIs and bounds

Paths are under `/api/v1/flights/jobs` unless stated otherwise:

| Endpoint | Contract |
|---|---|
| `GET /api/v1/flights/jobs` | Flights-only history; status filter; default 15 rows, size 1–100; created/ID descending |
| `GET /{job_id}` | Kind/version, filename, input SHA/size, status/timestamps/attempts, observation availability/count and issues |
| `GET /{job_id}/observations` | Exact raw rows/issues; logical-position order; default 25 rows, size 1–100 |
| `GET /{job_id}/discrepancies` | Summaries and complete filtered total; default attention, 25 rows, size 1–100 |
| `GET /{job_id}/discrepancies/{id}` | Complete `FieldEvidence`, candidates, raw claims, flags, baseline and digest |
| `GET /api/v1/jobs/{job_id}/download/input` | Shared original-input download |

Pagination starts at 1; beyond-end pages are empty with the same total. Discrepancy filters:
`attention`, `conflict`, `missing`, `uncertain`, `all`, plus one exact time `field`. Ordering is raw
flight then the four contract fields. Missing includes placeholders; categories overlap.
Attention excludes harmless formatting variation alone. Neither no flag nor source agreement
means verified correct. There is no dataset-wide flight-search or batch review-progress endpoint.

Complete grouped projections require a clean caller session and completed Flights v1 import;
keyset pages are 1–100 observations. Limits are **5,000 observations**, **250 claims per field**
and **64 candidates per field**. Empty/oversized/corrupt/inconsistent snapshots fail explicitly,
never return partial groups as complete evidence. List totals derive the complete bounded
selection before pagination; selected-scope requests avoid unrelated field graphs.

Upload errors: 400 bad filename, 413 size limit, 422 missing/invalid parameters or blocked hash.
Projection errors: 404 unknown job/scope; 409 wrong kind/version/state, corrupt evidence or bounds;
422 invalid pagination/filter; 503 safe storage errors. Failed/active jobs retain status access,
not a fabricated completed observation view. No client-controlled artifact paths are accepted.

## Conservative time normalization and grouping

Policy **`flight_time_normalization_v1`** returns exact raw text, status, optional canonical
clock/precision, qualifiers, reason and policy version. It never invents service date, timezone,
year, rollover or a complete timestamp. Parsing matches the entire string.

| Input | Result |
|---|---|
| `H:MM AM/PM`, optionally `:SS`; case/dots/spaces in meridiem | Parsed 24-hour clock; hour 1–12 |
| `noon`, `12:00noon`, `12:00 noon` | Parsed 12:00, minute precision |
| Bare hour 0 or 13–23, `H:MM` optionally `:SS` | Parsed 24-hour clock |
| Bare hour 1–12, including zero-padded | Ambiguous, `period_unspecified`, no canonical clock |
| Empty / whitespace-only | Missing, with distinct reasons and raw text retained |
| `Not Available` / `Contact Airline` | Placeholder, preserving which token appeared |
| Invalid components or any other full string | Unsupported, no guessed clock |

Digits are ASCII; minutes/seconds have two digits and valid ranges; whitespace around colons
is unsupported. Surrounding whitespace is allowed without changing raw text. `12:00 a.m.` is
00:00, `12:00 p.m.` is 12:00. Minute/second clocks serialize as `HH:MM`/`HH:MM:SS`, preserving
zero seconds. Fractions, leap seconds, 24:00, standalone midnight, compact A/P, dates, offsets,
weekday/status/runway/delay annotations and HTML-like text are not stripped or guessed.
Recognizable time plus extra context is `uninterpreted_context`, not an inferred timestamp.

Equivalence requires parsed results with the same current policy, canonical clock, precision
and qualifiers. `9:22 a.m.` and `09:22 AM` are equivalent; `21:22` and `21:22:00` are not established
equivalent. **Failure to prove equivalence does not prove disagreement.**

Groups use `(job_id, exact raw flight)`, never combine snapshots or normalize flight/source IDs.
Missing or flight-flagged records stay explicitly ungroupable with full claims/issues; no invented
entity collects blank identities. Blank/flagged source IDs remain visible but do not add usable
source counts. Groups sort by job/flight, claims by position/tuple ID and sources lexically.
Repeated tuple/position identities are integrity errors, not silent deduplication.

## Field evidence and source support

Policy **`flight_discrepancy_v1`** independently examines each `(job, flight, time field)`:

- **Equivalent:** positive normalization equivalence.
- **Confirmed conflict:** both parse, precision/qualifiers match, canonical clocks differ.
- **Incomparable:** everything else, including unsupported, ambiguous or different-precision claims.

Orthogonal flags expose conflict, missing, placeholder, ambiguity, unsupported context, formatting
variation, incomparable clocks, unusable source identity, internal source conflict and insufficient
corroboration. They can coexist; no quality/confidence score collapses them.

Only parsed equivalent clocks form candidates. Each preserves canonical value, precision,
qualifiers, raw spellings, supporting observation/source IDs and both counts. It separately names
contradicting candidate/claim IDs, incomparable candidates and nonparsed context. Parent claims
resolve references to exact raw values, source/position, normalization and identity issues.
Repeated reports add observations, not distinct-source votes. Opaque source IDs imply neither
reliability nor independence. Internal comparable contradictions from one source remain visible.

Baseline **`flight_source_support_baseline_v1`** proposes only a unique plurality leader with at
least two distinct usable source IDs. It abstains on ties, no/insufficient support, ambiguous or
unsupported claims, incomparable clocks, unusable sources or internal contradictions. Missing/
known placeholders alone do not veto a qualifying proposal. Candidates sort lexically, not by
confidence. Every baseline is non-authoritative; plurality is not truth or a human decision.

`fld_` scope IDs and `cand_` candidate IDs use canonical JSON/SHA-256, not process `hash()`.
They include scope/policy and candidate semantics. Candidate IDs can stay stable while support
changes. `evidence_digest` hashes full evidence except itself: raw claims, issues, positions,
relations, flags, baseline and policies. Changes invalidate freshness without inventing a new
scope. Derived evidence is deterministic and recomputed without database writes.

## Human review and history

Policy **`flight_human_review_v1`**. Under a discrepancy: `GET /review`, `POST /review`, and
`GET /review/history` (chronological, default 25, size 1–100). A write requires current
`expected_evidence_digest`, `expected_revision`, an 8–80 character ASCII letter/digit/underscore/
hyphen `request_id`, action and local `reviewer_label`. Strict unknown/type validation applies;
label/rationale/manual limits are 80/1,000/160 characters. Labels are not authenticated identities.

| Action | Required selection and effect |
|---|---|
| accept | Only current validated proposed AI `investigation_id`, matching scope/digest/config; its candidate/citations are revalidated |
| override | Rationale plus exactly one current `candidate_id` or parsed `manual_value`; works without AI |
| reject | Current valid proposal investigation and rationale; records rejection without an approved value |
| unresolved | Optional rationale, no candidate/manual/investigation selection; no approved value |

An override may optionally link a current valid proposal; omit that link for abstention/failure.
Manual input uses unchanged normalization v1 and must be parsed/unambiguous. Exact entered text,
canonical value/precision/qualifiers remain metadata; origin is `human_assertion` with empty source
support. Observed selections retain real support and origin `observed_candidate`.

Effective states: unreviewed, accepted, overridden, rejected, unresolved. Later events supersede,
never overwrite/delete, earlier revisions. Changed evidence makes the old decision stale, current
state unreviewed and effective value null; re-review uses the latest revision and new digest.
A later provider outage alone does not revoke an explicit approval over unchanged evidence.

Revisions start at 1 (initial expected revision 0). Unique scope/revision and globally unique
request IDs plus payload fingerprints prevent lost updates and conflicting reuse. Exact retries
return their original event even after later revisions. New writes rebuild evidence, validate and
insert atomically under the short shared review/export publication gate. Stale digest/revision,
invalid/stale AI or conflicting request reuse is 409; invalid value/payload is 422; database failure
is 503. An uncertain acknowledgement requires the same request/payload, not a fresh decision ID.

## Frozen exports

Policy **`flight_reviewed_export_v1`**. Under `/api/v1/flights/jobs/{job_id}/exports`:
`GET /snapshot`, `POST` with `expected_snapshot_digest` and `request_id`, paginated `GET`
(default 25, size 1–100), `GET /{export_id}` and `GET /{export_id}/download/{artifact}`.
Allowlisted artifact labels are `reviewed`, `exceptions`, `provenance`; listing is newest first.

Snapshot identity covers input hash, contract/policies, field digests, effective decision IDs/
revisions/resolutions and observation mappings, including ungroupable/unmapped history.
One SQL statement captures the latest revision vector. Files are generated outside a transaction;
rebuilding the snapshot under the shared job lock before metadata commit rejects changed state.
An exact export retry returns the original frozen result even after later decisions; changed
request reuse or expected snapshot mismatch is 409. Later reviews never mutate existing exports.

| Artifact | Exact contract |
|---|---|
| `reviewed.csv` | `job_id,export_id,flight`, then for each of the four fields in contract order: `{field},{field}_status,{field}_decision_id,{field}_revision` |
| `exceptions.csv` | `job_id,export_id,flight,field,discrepancy_id,review_status,reason,decision_id,revision,tuple_id,src,row_number` |
| `provenance.json` | Export/time/snapshot/input hash, contract/policies, field evidence/digests, effective review metadata and canonical origin/support, exact tuple/source/position mappings, ungroupable issues and unmapped decisions, CSV hashes/sizes |

One reviewed row represents a groupable flight. Only current accepted/overridden human decisions
fill canonical approved values. Rejected/unresolved/unreviewed/stale fields stay empty with explicit
status; even undisputed agreement is not silently approved. Absent decision revision is 0 with no
ID. Canonical clocks are already interpreted; do not reparse them as ambiguous raw bare clocks.

Exceptions includes every unapproved field (`no_human_approved_value` / `stale_review`) and each
ungroupable observation, without invented group IDs. Provenance maps each group field to original
`(job, tuple_id, field)` cells; never align by row order. Manual assertions invent no supporting
reports. API metadata hashes all three artifacts; a manifest cannot recursively hash itself.
Fixed snapshot/UUID/time renders identical bytes; a new UUID/time intentionally changes bytes.

Files use `OUTPUT_DIR/flight-reviewed/{server_uuid}/` and fixed names. Exclusive pending files
are flushed/fsynced before rename; successful metadata publication alone makes them downloadable.
Stale generation and duplicate losers clean only their own artifacts. Ambiguous commits retain
files because metadata may already exist; orphan retention needs deliberate ownership review.
Download labels/UUIDs/root/symlinks, bounded sizes and SHA-256 are checked. Missing artifacts are
404, corrupt/stale layout 409, oversized generation 413, storage failures 503. Existing downloads
never regenerate artifacts. Bounds: 20,000 fields and 32 MiB combined artifacts, no partial output.

Spreadsheet presentation prefixes one apostrophe for formula markers, leading apostrophe,
whitespace/BOM or controls; removing exactly one prefix reverses it. Standard CSV quoting handles
newlines. JSON retains exact identities; source storage is never escaped/rewritten. Files are
application-immutable, not OS-WORM or authenticated proof. See [offline evaluation](AI_AND_EVALUATION.md).

## Transaction compatibility

The unadvertised `/legacy/transactions?job=ID` retains the original intake/explorer/correction
feature; it is not the current Flights contract. Owners remain `app/intake/{schemas,processing}.py`,
`app/records/`, `app/analytics/` and the original frontend `AppShell`/panels.

Its 12 fields are customer_id, email, country, signup_date, order_amount, currency, payment_method,
order_status, product_category, quantity, discount_percent, last_login_date. Structural/email/date,
finite nonnegative amount, positive quantity and 0–100 discount rules apply. Dates use `%Y-%m-%d`;
countries are DE/FR/IN/US/GB, currencies EUR/USD/INR, methods card/paypal/bank_transfer and states
completed/pending/cancelled. DE/FR
require EUR, completed orders require nonzero amounts, last login cannot precede signup. Repeated
customers are allowed; later normalized duplicate full records are rejected. Missing/duplicate
headers and row widths fail; extra mapped columns are ignored. Accepted values normalize case,
whitespace, dates and two-decimal amounts; rejected values retain explanations. No FX conversion
or aviation normalization belongs here.

Deterministic quality weights remain validity 60%, completeness 20%, uniqueness 10%, anomaly
health 10%; dimension percentages round to two decimals and overall to one. Anomaly heuristics
(amount >1,000 in its own currency, quantity >20, discount >50) do not reject records. If no accepted
rows, anomaly health is unavailable and other weights renormalize; failed/empty jobs do not get a
fabricated score. Aggregate-only legacy AI is separate from Flights investigation.

Preview checks only the first ten records, not full-file duplicates. Versioned mapping/templates
snapshot each job's options; mapping source columns must be unique (100 columns, 200 characters
per header). Declarative optional rules cannot disable base validation or execute code. Record
queries/export share status/search/category/sort; full filtered export is not limited to the page.
Historical jobs without an index remain downloadable and are not silently rebuilt.

Corrections edit rejected known fields only, require validation, and create child jobs with copied
original bytes plus cumulative overlays; they never overwrite parent files/analytics. Full worker
revalidation can still reject a duplicate. Bounds: 200 edited records, 10,000 characters/cell,
1 MiB submitted values; cumulative JSON stays within the upload cap. Malformed row widths require
source-file repair. Legacy drafts have their own navigation protection.
Maintenance endpoints remain `/api/v1/imports/preview`, `/imports/templates`, `/jobs/{id}/records`,
`/records/export`, `/corrections/validate` and `/corrections` (POST accepts a new job, 202).
See [manual sample fixtures](../backend/samples/manual/README.md), not the Flights uploader.
