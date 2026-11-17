# Flights discrepancies, evidence and candidates — Milestone 5

This is deterministic observed-data investigation. Candidates and baseline
proposals are possible values, not corrected data or known truth. No AI, decision
state, repair, reviewed export, benchmark evaluation or derived persistence exists.

## Execution and ownership

```text
Immutable Flights observations
  → existing load_grouped_flights (bounded read-only snapshot)
  → existing group_flights / flight_time_normalization_v1
  → investigate_field(group, field)
  → typed frozen FieldEvidence + candidates + baseline + digest
  → discrepancy summary list or complete selected evidence
```

`app/reconciliation/evidence.py` is pure computation. It imports only standard
library code and the existing pure grouping/normalization types/functions.
`app/reconciliation/routes.py` owns HTTP projection and calls the existing bounded
loader; database code does not decide comparison semantics. Main application
composition adds only router registration. Intake, workers, persistence models,
migrations, legacy contracts and frontend code are unchanged.

## Comparison and queue policy

Detection policy: **`flight_discrepancy_v1`**. Normalization remains
**`flight_time_normalization_v1`**, unchanged from Milestone 4.

Every investigation is one `(job_id, exact flight identifier, time field)`, using
the four contract fields independently. A field claim retains tuple ID, logical
position, exact source ID, source usability, all identity issues, and the full
NormalizedTime result (including unchanged raw text, status, reason and qualifiers).

`compare_times` has three outcomes:

| Outcome | Meaning |
|---|---|
| equivalent | Existing equivalent_times positively establishes equivalence |
| conflict | Both clocks parse under current normalization, precision/qualifiers match, canonical clocks differ |
| incomparable | All other comparisons; absence of established equivalence does not prove disagreement |

Different precision remains incomparable even when minute components differ.
There is no interval reasoning, seconds truncation, date inference or annotation
removal. Ambiguous, missing, placeholder and unsupported text cannot become
competing clock candidates. Exact raw variation alone is not a semantic conflict.

Orthogonal flags expose confirmed conflict, missing claims, placeholders, ambiguous
claims, unsupported claims, harmless formatting variation, incomparable supported
values, unusable source identity, internal source conflict and insufficient source
support. StatusCounts separately counts all five normalization states. These
conditions can coexist and are not collapsed into a severity or quality score.

The default attention queue includes any flag except formatting variation alone.
Consequently a fully parsed, equivalent field with at least two usable sources
is not an unresolved error just because spelling differs. A lone supporting source
is discoverable as insufficient corroboration. This is a workflow policy, not
ground-truth error detection. `kind=all` can inspect normal fields too.

## Candidate evidence and source counting

Only parsed claims form candidates, grouped exclusively by equivalent_times.
Every candidate exposes:

- Scope-stable candidate ID, canonical clock, precision and qualifiers.
- All distinct supporting raw spellings and supporting tuple IDs.
- Sorted usable source IDs, observation count and distinct-source count.
- Contradicting candidate IDs and their supporting observation IDs.
- Incomparable candidate IDs, separate from contradictions.
- Context observation IDs for missing, placeholder, ambiguous or unsupported text.
- Detection and normalization policy versions.

Claims in the parent FieldEvidence resolve every reference to raw text, source,
position, normalization and issues. No raw record is lost when it cannot support
a candidate. No-supported-candidate is an explicit candidate_state.

Source usability follows Milestone 4: nonblank raw ID, no stored src issue.
Unusable-source observations remain visible and can support an observed clock,
but do not add a usable-source vote. Repeated identical claims from one source
increase observation count, not distinct-source support. Source IDs are opaque;
no trimming, reliability score, authority assumption or independence claim occurs.

When a usable source supports candidates with confirmed incompatible clocks,
internally_inconsistent_source_ids names it. Both claims and descriptive support
counts remain visible. Precision-incomparable claims are not mislabeled as a
proven internal contradiction. The baseline abstains on either condition.

## Single deterministic baseline

Policy: **`flight_source_support_baseline_v1`**.

A proposal requires a unique candidate with the highest distinct usable-source
support and at least two such source IDs. This is a plurality rule; it does not
require a majority of all reporters. Counts describe source IDs, not statistically
independent confirmations. Candidate display order is lexical clock/precision/
qualifiers, not a ranking or confidence score.

The policy abstains with explicit reasons for any of:

- No supported candidate.
- Ambiguous or unsupported claims anywhere in that field.
- Incomparable supported precision/context.
- Unusable source identity.
- Internal source contradiction.
- Tied highest distinct-source support.
- A unique leader supported by fewer than two usable source IDs.

Missing and known placeholders alone do not veto a qualifying proposal; they remain
counted and keep that field in the attention queue. Parsing uncertainty is treated
conservatively as material, without support-percentage thresholds or reference
tuning. All baseline responses carry authoritative=false. There is no automatic
repair, approval, mutation or claim that the proposed clock is correct.

## Stable identities and evidence digests

IDs use SHA-256 of canonical UTF-8 JSON, sorted object keys and compact separators;
Python hash() is not used. Scope IDs (`fld_` prefix) include detection policy,
normalization policy, job ID, raw flight and field. Candidate IDs (`cand_` prefix)
add canonical clock, precision and qualifiers to that scope.

Candidate identity does not change merely because support changes while its
semantic value remains. evidence_digest is `sha256:` plus the digest of the full
FieldEvidence payload excluding the digest itself. It includes raw claims, issues,
provenance positions, candidates, flags, summaries, baseline and policy versions.
Raw/support changes therefore invalidate the digest while preserving scope IDs.
Future AI must bind to that digest and authorize candidate/source references; no
AI request or stale-recommendation operation is implemented in this milestone.

Claims sort by row position/tuple ID; candidate clocks, raw spellings, source IDs
and evidence-reference lists have explicit deterministic ordering. Source input
iteration order and Python hash seeds do not change substantive evidence or IDs.

## Read-only API

| GET endpoint | Response |
|---|---|
| `/api/v1/flights/jobs/{id}/discrepancies` | Typed DiscrepancyPage with bounded summaries, filtered total, page metadata, ungroupable count and existing raw-observation URL |
| `/api/v1/flights/jobs/{id}/discrepancies/{discrepancy_id}` | Complete typed FieldEvidence for that scope, including claims, candidates, relations, baseline and digest |

List defaults: page=1, page_size=25, kind=attention. Page size is 1–100.
Beyond-end pages are empty without changing the filtered total. Optional `field`
is restricted to the four time fields. Kinds:

- `attention`: the default queue policy above.
- `conflict`: confirmed comparable-clock conflict.
- `missing`: missing or placeholder evidence.
- `uncertain`: ambiguity, unsupported values, precision incompatibility, unusable
  source identity, internal source conflict or insufficient source support. A
  tie between otherwise comparable conflicting clocks remains a conflict; tie
  abstention alone is not parsing/comparison uncertainty.
- `all`: includes normal fields.

Ordering is raw flight followed by contract field order. Summary entries include
IDs, counts, flags, candidate count, concise description, baseline and digest.
Ungroupable observations do not acquire invented flight scopes: their count and
the paginated raw-observation URL make those exceptions explicit.

Missing job/unknown or wrong-snapshot scope → 404. Wrong kind, unfinished/failed
job, unsupported version, exceeded limits or inconsistent stored state → 409.
Invalid pagination/filter/field/path parameters → 422. Database access failures
→ 503 with a safe message. Malformed stored issue/claim diagnostics are not echoed.
No writable discrepancy endpoints exist.

## Bounds and limitations

The existing 5,000-observation snapshot cap and database pages of at most 100 rows
remain intact. Complete per-field evidence additionally caps at 250 observations
and 64 candidates to bound full claim payloads and pairwise candidate-reference
graphs. These are engineering bounds, not tuned decision thresholds. Exceeding
them fails explicitly: no truncated evidence is returned. Field filters and selected
scope requests build only the requested field/scope graphs; an unrelated field's
candidate limit does not prevent selected in-bound evidence retrieval.

List processing derives selected fields on demand before pagination so totals and
queue flags are complete. Repeated requests recompute the bounded snapshot;
there is no cache, background job, derived table or global all-datasets query.
This supports the narrow benchmark scale. Complete HTTP evidence is not itself
an approved LLM prompt budget; Milestone 6 needs a separate bounded request and
strict candidate/citation validation plus abstention/failure behavior.

## Verification and safety

Synthetic tests cover comparison versus uncertainty, equivalent raw spellings,
mixed missingness, per-field/job scope, repeated sources, internal contradictions,
baseline vetoes and ties, no-candidate states, stable IDs/digests, limits and typed
APIs. API checks verify no database DML and unchanged job/import/observation rows
and original bytes. Pure code imports run with runtime/reference dependencies
denied. Earlier tests remain unchanged.

```bash
timeout 120s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests/test_flights_evidence.py backend/tests/test_flights_discrepancy_api.py -q
timeout 120s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests -q
python3 -B -m unittest discover -s scripts -p test_flights_benchmark.py -q
git diff --check
```

Existing fixtures isolate SQLite/files, use memory transport and disable AI.
TestClient lifespan migrations affect only disposable state. No reference files,
label fixtures, real benchmark evaluation, normal server startup, Docker operation,
development migration, provider call, new dependency, commit or push is required.
Live PostgreSQL/Redis/Celery integration remains unverified.

Observed results: 20 focused evidence/API tests, 204 full backend tests, and 13
benchmark foundation tests passed; `git diff --check` passed. Backend tests used
the previously verified TestClient sandbox exception with the same disposable
fixtures. All prior milestone content was preserved; main.py adds only the new
router import and registration. Work remains on feat/reconciliation-workbench.
