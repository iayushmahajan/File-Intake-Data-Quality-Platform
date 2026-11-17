# Flights time normalization and grouping — Milestone 4

This adds computed, read-only interpretation of immutable `raha_flights_v1`
observations. Parsed clocks are interpretations, not corrections or ground truth.
There is no conflict detection, voting, candidate generation, AI, review, export,
reference evaluation, new HTTP endpoint, migration, or derived-data persistence.

## Ownership and execution

- `app/reconciliation/normalization.py`: standard-library pure clock interpretation
  and positive equivalence checks.
- `app/reconciliation/grouping.py`: pure grouping of intake-validated observation
  copies, retaining identities, claims and all stored issues.
- `app/reconciliation/observations.py`: bounded, read-only SQLModel projection of a
  completed Flights import into those pure types.

```text
Existing completed job + immutable FlightObservation rows
  → load_grouped_flights(session, job_id, batch_size=100)
  → keyset database pages → frozen RawObservation copies
  → group_flights → normalize_time for each of four field claims
  → GroupedFlights(groups, ungroupable)
```

No production caller was added to the worker or API. This small internal service
is the integration seam for Milestone 5; tests exercise it against actual persisted
synthetic imports. Existing raw-observation responses stay unchanged. Transaction
`transform_row`/`prepare_row` own customer/order/date rules and remain untouched;
no useful clock-specific helper was found there.

## Normalization policy

Stable identifier: **`flight_time_normalization_v1`**.

`normalize_time(raw: str) -> NormalizedTime` returns a frozen dataclass containing:
exact `raw`, `status`, optional `canonical_clock`, optional `precision`, a tuple of
`qualifiers`, a deterministic `reason` for non-parsed outcomes, and `policy_version`.
No date, timezone, service date, day rollover, airport, or calendar year is inferred.
`canonical_clock` is a clock string, never a complete timestamp.

| Input grammar | Result |
|---|---|
| `H:MM AM/PM`, optionally `:SS` | Parsed 24-hour clock; explicit hours must be 1–12 |
| Meridiem case, optional dots, spaces/tabs before meridiem/between its letters | Equivalent supported spellings, e.g. `9:22 a.m.`, `09:22 AM`, `9:22 A. M.` |
| `noon`, `12:00noon`, `12:00 noon` (case-insensitive) | Parsed `12:00`, minute precision |
| Bare `H:MM`, optionally `:SS`, hour 0 or 13–23 | Parsed 24-hour clock, e.g. `00:15`, `14:25` |
| Bare clock hour 1–12, even zero-padded | Ambiguous; `period_unspecified`; no canonical clock |
| Empty or whitespace-only | Missing; exact raw text retained, with different explanatory reasons |
| `Not Available`, `Contact Airline` | Placeholder; separate qualifier records which token appeared |
| Out-of-range components | Unsupported/invalid; no canonical clock |
| Any other text | Unsupported; no guessed canonical clock |

Parsing permits surrounding whitespace but never changes `raw`. Digits are ASCII,
hours are one or two digits, minutes/seconds exactly two, and supported components
must be in range. No whitespace around colons is accepted. Meridiem punctuation
consists of optional dots after its letters. Placeholders allow case and surrounding
whitespace differences, without collapsing internal text. `12:00 a.m.` becomes
`00:00`; `12:00 p.m.` becomes `12:00`. Missing never becomes midnight.

Minute clocks serialize as `HH:MM`; second clocks as `HH:MM:SS`. Seconds are retained
even when zero. Fractional seconds, leap seconds, `24:00`, standalone `midnight`,
compact `A`/`P` meridiems, and natural-language formats are unsupported in v1.

Full-string matching prevents loss of context. Dates, weekday/month annotations,
offsets, estimates/runway annotations, delays/statuses, trailing markers, and
HTML-like text remain unsupported. Recognizable clock-like text with extra context
receives `uninterpreted_context`; no context substring is stripped or asserted to
be a timezone/date. `Dec 2 Not Available` is not silently reduced to a placeholder.
Non-ASCII text and markup remain plain raw strings, never executable content.

Grammar choices were informed only by the existing dirty-only format-shape report:
dotted meridiems, bare clocks, noon, placeholders, and numerous annotated forms.
No reference answers or dirty/reference error locations were consulted for rules.
The policy prioritizes explicit clocks over annotation coverage.

## Equivalence

`equivalent_times(left, right)` is true only when both results are parsed under the
current v1 policy and their canonical clock, precision and qualifiers match.

- `9:22 a.m.` equals `09:22 AM`.
- `9:22 p.m.` equals `21:22`.
- `9:22:07 p.m.` equals `21:22:07`.
- `21:22` is not established equivalent to `21:22:00`: precision differs.
- Bare `9:22`, placeholders, missing values and unsupported values never become
  parsed equivalents, even when their raw strings are identical.
- Different policy versions cannot establish equivalence through this helper.

**False means equivalence was not established; it does not prove disagreement.**
Milestone 5 must inspect status/precision and preserve non-parsed cases separately.
This helper neither ranks values nor decides which observation is correct.

## Grouping contract

`group_flights(Iterable[RawObservation]) -> GroupedFlights` is pure. Inputs must
originate from validated Flights intake, including complete stored identity issues.
It does not parse new CSVs or independently revalidate flight syntax with another
regex. This makes the Milestone 3 identity policy the source of truth.

`RawObservation` holds job ID, opaque tuple ID, logical row position, source, raw
flight, all four raw time strings, and frozen issue copies. `ProjectedObservation`
holds that raw copy plus four ordered `TimeClaim(field, NormalizedTime)` values.

Each `FlightGroup` has `(job_id, exact raw flight)` identity and ordered projected
observations. Its properties expose observation IDs/count, source references
(`src`, tuple IDs and row positions), and distinct source count. The same raw
flight in different jobs is always a different group. No trimming/case folding,
deduplication, majority computation, confidence score or source weighting occurs.

Blank/whitespace-only flight IDs yield `missing_flight` ungroupable records. Any
stored issue whose field is `flight` yields `flagged_flight`, including a spelling
that superficially looks valid. Ungroupable records retain all values, issues and
normalized claim projections; blank flights never become one invented entity.

Blank or source-flagged IDs do not contribute to source references/counts. Their
observations still belong to a usable flight group and remain fully visible there.
Counts describe distinct nonblank, unflagged raw source IDs, not independence or
reliability. Source copying/shared feeds remain unknown. Multiple claims from one
source retain their separate tuple IDs and positions.

Groups sort by `(job_id, raw flight)`; observations within each group by
`(row_number, tuple_id)`; source references by exact source string; ungroupable
records by `(job_id, row_number, tuple_id)`. Field claims use the contract's four
time-field order. Input iteration order cannot alter membership or output order.
Logical position is presentation/provenance metadata, not observation identity.
Repeated `(job_id, tuple_id)` or `(job_id, row_number)` input is a programming/data
integrity error and raises ValueError; it is never silently deduplicated.

## Bounded persisted projection

`load_grouped_flights` accepts a caller-owned clean session and a completed Flights
job with contract version 1. It reads by logical-position keyset pages of 1–100
rows and returns a complete snapshot only. The current explicit ceiling is 5,000
observations; larger imports fail with ValueError rather than returning incomplete
groups. No partial group page should be used as complete discrepancy evidence.

Unknown job raises LookupError. Wrong kind, unfinished/failed job, unsupported
version, invalid page size, count mismatch, oversized/empty snapshot or pending
session writes raise ValueError. A missing/corrupt metadata situation is not
silently treated as an empty successful analysis. The service neither flushes nor
commits; it disables autoflush and rejects a dirty session before reading.

The cap supports the current narrow benchmark. Larger-snapshot access, caching,
derived persistence, any HTTP projection and interpretation of annotated contexts
require deliberate later decisions; none are prerequisites of this milestone.

## Verification and safety

All behavioral fixtures are synthetic. Tests cover grammar, ambiguity, precision,
raw preservation, policy equivalence, snapshot/source boundaries, ordering,
ungroupable issues, and complete groups across database pages. Integration checks
verify no INSERT/UPDATE/DELETE during projection and unchanged persisted rows,
job metadata and original bytes. Pure-module imports are also tested with runtime,
database, provider and offline-inspector imports explicitly denied.

The backend conftest still isolates SQLite/files and disables live providers before
application imports. TestClient migrations run only against disposable fixtures.
No normal server, development migration, Docker stack, provider call, reference
file access or operational storage change is needed. No dependencies were added.

```bash
timeout 120s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests/test_flights_normalization.py backend/tests/test_flights_grouping.py backend/tests/test_flights_intake.py -q
timeout 120s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests -q
python3 -B -m unittest discover -s scripts -p test_flights_benchmark.py -q
git diff --check
```

Backend runs use the previously verified sandbox exception for TestClient's thread
bridge, while retaining the same disposable fixtures. Live PostgreSQL/Redis/Celery
transport remains unverified; normalized values are not measured repair outcomes.

Observed verification: 61 focused normalization/grouping/intake tests, 184 full
backend tests, and 13 benchmark foundation tests passed. `git diff --check` passed.
All 18 pre-existing Milestone 2–3 paths remained byte-identical on the dedicated
`feat/reconciliation-workbench` branch; this milestone adds seven files only.
