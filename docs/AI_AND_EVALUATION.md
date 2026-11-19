# AI assistance and offline evaluation

AI is optional, explicitly requested and non-authoritative. Deterministic parsing/evidence,
source support and review validation remain backend responsibilities. A model may propose one
observed candidate or abstain; only an explicit human action can approve a value. No real-provider
quality improvement or authentic frozen benchmark repair accuracy has been demonstrated.

## Evidence-bounded investigation

Owners: `backend/app/reconciliation/ai.py`, `investigations.py`, `investigation_routes.py`.
Policies are `flight_investigation_v1`, `flight_investigation_prompt_v1` and
`flight_recommendation_v1`, alongside the normalization/discrepancy versions.

Under `/api/v1/flights/jobs/{job_id}/discrepancies/{discrepancy_id}/investigations`:

- POST accepts only `expected_evidence_digest` (`sha256:` + 64 lowercase hex digits) and
  `request_id` (8–80 ASCII letters/digits/underscore/hyphen).
- GET returns latest state or `not_requested`; GET `/{investigation_id}` returns selected history.
- The server rebuilds evidence, never trusts client-supplied values/claims, rejects stale evidence
  before calling the provider, and checks evidence/configuration again after completion.
- Eligibility requires a supported candidate plus conflict, ambiguity, unsupported claims or
  incomparable supported precision/context. Agreement, missingness alone and no-candidate cases
  do not justify a call. Budget/eligibility refusal is explicit, not silent sampling.

One complete selected-field payload includes scope/digest/flight/field, policies, flags/counts,
raw time claims/normalization reasons, identity issue codes and every authorized candidate with
precision/qualifiers, support, contradiction, incomparability and context references. Source IDs
are stable job-scoped SHA-256 aliases, not reliability scores; claim IDs bind scope, digest and
tuple ID. API responses map citations back to actual stored observations. The baseline is omitted
to reduce anchoring. Other columns/datasets, filenames, arbitrary issue text, secrets, reference
labels and evaluation results are excluded.

Untrusted values are JSON data in a user message separate from system instructions prohibiting
embedded instructions. The model has no tools, browsing, file or database access. Returned text
is displayed as escaped plaintext. These measures and reference checks do not prove free-text
reasoning faithful, nor establish historical truth.

| Budget | Current bound |
|---|---:|
| Claims / candidates | 32 / 8 |
| Raw claim UTF-8 bytes | 160 each |
| Complete serialized input with instructions/schema | 32,000 bytes |
| Completion tokens | 2,048, including reasoning where supported |
| Accepted received content | 16,384 UTF-8 bytes |
| Explanation / uncertainty | 1,200 / 800 characters |
| Supporting / contradicting citations | 16 / 16 |
| SDK timeout / total asynchronous deadline | 20 / 30 seconds |
| Automatic SDK retries | 0 |
| Reserved attempts per scope/digest/config | 3 |
| Global concurrent claims / lease | 2 / 90 seconds |

Exceeding any input bound refuses the whole request. Bytes are not a precise token estimate;
actual usage is retained when reported. Transport receives a response before validating its
content-size limit. No invented cost/confidence figures or hidden retry/repair loop exist.

## Strict output and truthful states

Exactly six required fields, no extra/duplicate JSON keys:

```json
{"recommendation":"propose","candidate_id":"authorized-id","supporting_claim_ids":["supplied-id"],"contradicting_claim_ids":[],"explanation":"Bounded explanation","uncertainty":"Bounded limitations"}
```

Strict types, nonblank bounded text, controls, bounded unique citations and allowed recommendation
values are checked. A proposal needs one current authorized candidate and at least one supplied
claim truly supporting it. Contradictions must be supplied **confirmed** contradictory claims;
ambiguous/context evidence cannot become a contradiction. An abstention must use `abstain`, null
candidate and empty citation lists. Free-form times, fabricated/cross-scope references and wrongly
attributed support fail. Structural grounding is not proof of prose entailment or correctness.

All responses have `authoritative: false`. Running operations return 202; terminal outcomes 200.
Stored outcomes distinguish `running`, `proposed`, `abstained`, `unavailable`, `invalid_response`,
`failed`, `stale` and preflight `ineligible`. `not_requested` is a read projection, not a row.
Truncation/refusal/malformed JSON/schema/citations/oversized output is invalid_response; timeout
is failed/provider_timeout; rate limits/provider API failure is unavailable; unexpected SDK error
is failed/provider_failure. None is relabeled genuine abstention. Stale history can retain its
validated old recommendation but has `current: false`, stale status and a separate stored_status.
GET rechecks freshness without writing, including unprojectable evidence or changed configuration.

404 denotes unknown scope/history, 409 stale digest/bound request-key conflicts, 422 bad request,
503 safe persistence failure, and 429 capacity exhaustion with Retry-After 5. Existing job/type/
version/completion/projection guards still apply. No private provider exception is exposed.

## Provider adapter and persistent claims

Existing `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` configure a narrow AsyncOpenAI Chat
Completions call (pinned SDK in `backend/requirements.txt`). Placeholder configuration only:

```dotenv
OPENAI_API_KEY=<local-secret>
OPENAI_BASE_URL=https://<compatible-host>/v1
OPENAI_MODEL=<supported-chat-model>
```

The request uses `max_completion_tokens`; plain JSON is requested and validated locally.
It assumes no provider-specific response_format, temperature or tool support. Incompatible
parameters fail safely. URL credentials/queries/fragments and invalid model identifiers are
rejected. Dedicated Compose leaves the key empty and clears inherited host configuration;
see [development](DEVELOPMENT.md). No provider/model is claimed live-compatible or cost-validated.

Rows record scope/digest, provider/model/config fingerprint, policies, request identity, attempt,
claim token/lease/slot, outcome, validated result/citations, safe response identity, usage/timestamps
and input hash/byte count. Full prompts and raw/unvalidated responses are not persisted/logged.
Short transactions reserve/publish; no transaction spans the provider await. Conditional token/
lease checks fence late results. Unique request IDs, nullable global slots, one running scope
and charged ordinals bound concurrent processes; PostgreSQL contention remains unverified.

A bound-key replay returns its original outcome, including failure. Successful proposals/valid
abstentions are cached by evidence/config; cache/running hits bind only the returned row's request
ID, not an alias for the caller's unused key. A post-claim cache recheck avoids a second provider
call but conservatively consumes its reserved ordinal without duplicating usage. Explicit failure
retry needs a new ID and another bounded reservation; crash-before-send still consumes an attempt.
Changing model/policy changes the budget scope. Expired running rows appear failed/interrupted
on GET without a write; a later POST may reap/reserve. There is no automatic second queue/retry.
An interrupted request can leave uncertain billing; bounded claims are not exactly-once charging.

## Dataset provenance

The unchanged [source manifest](flights-source-manifest.json) pins BigDaMa/raha commit
`7be1334b8c7bbdac3f47ef514fb3e1e8c5fc181c` (2025-06-05), last Flights change
`82f3323c02f32b1154342d76cbcd3cdeb2233914` (2019-11-07), observed/reference Git blob identities,
SHA-256, byte counts and retrieval on 2026-11-11. CRLF bytes were preserved. Observed data has
2,376 records, 100 flight keys, 38 source strings and 9,504 time cells, including 2,370 empty cells.
Source IDs are not proof of independent reporting. Historical reference inspection found 4,920
exact differing time cells (911 scheduled departure, 1,558 actual departure, 1,100 scheduled arrival,
1,351 actual arrival); this is input characterization, not product repair performance.

Research attribution:

- Mahdavi et al., *Raha: A Configuration-Free Error Detection System*, SIGMOD 2019,
  [DOI](https://doi.org/10.1145/3299869.3324956).
- Mahdavi and Abedjan, *Baran*, PVLDB 13(11), 2020,
  [paper](https://www.vldb.org/pvldb/vol13/p1948-mahdavi.pdf), Section 6.1/Table 2.
- Li et al., *Truth Finding on the Deep Web: Is the Problem Solved?*, VLDB 2013,
  [authors' record](https://arxiv.org/abs/1503.00303); research lineage, not a verified byte-level derivation.
- Rekatsinas et al., *HoloClean*, PVLDB 10(11), 2017, pp.1190–1201, as cited by Baran.

The pinned upstream project declares Apache-2.0, but dataset-specific/underlying third-party
collection and redistribution permissions were not established. Public availability/paper licensing
does not settle them. Keep raw files local-only; do not commit/bundle datasets or publish reference
answers. Prefer synthetic public demonstrations pending rights review. Existing limited documentation
screenshots are not redistribution clearance. No root project license is invented by these notices.

Keep external private (0700 directories / 0600 files) benchmark storage separate from the repository,
application DATA_DIR, served paths and container mounts: `observed/dirty.csv` and, only for offline
research, `reference/clean.csv`. Obtain the exact commit-pinned observed URL from the manifest and
verify SHA-256/154,776-byte length before use. Do not fetch the clean file for operational setup.
The optional shell variable FLIGHTS_BENCHMARK_ROOT is a command convenience, not an app setting:

```bash
FLIGHTS_BENCHMARK_ROOT=/absolute/external/benchmark
python3 -B scripts/inspect_flights.py --benchmark-root "$FLIGHTS_BENCHMARK_ROOT"
# Offline-only, with an explicitly isolated reference:
python3 -B scripts/inspect_flights_reference.py --benchmark-root "$FLIGHTS_BENCHMARK_ROOT" --reference "$FLIGHTS_BENCHMARK_ROOT/reference/clean.csv"
```

Inspectors reject repository/symlink redirection. Dirty inspection never opens a reference;
reference integrity joins opaque tuple IDs, not row order, and requires a bijection and matching
source/flight identities. A consistent historical reference does not certify aviation truth.

## Frozen-output offline evaluation

Entry: `scripts/evaluate_flights.py`, policy `flight_offline_evaluation_v1`, evaluator 1.0.0.
It is file-only: no runtime API, database, worker, provider or operational reference-loading path.
Save the published export metadata response separately plus unchanged reviewed/exceptions/provenance
artifacts. Metadata hashes are a trust anchor, not an authenticated signature of review or AI execution.

```bash
python3 -B scripts/evaluate_flights.py \
  --export-dir /external/frozen-export \
  --metadata /external/export-metadata/metadata.json \
  --dirty /external/benchmark/observed/dirty.csv \
  --reference /external/benchmark/reference/clean.csv \
  --output /external/evaluation-results/run-001.json
```

All placeholders require explicit paths. Inputs are regular/non-symlink files outside the repository
and exported DATA_DIR; operators must exclude custom runtime mounts the file-only process cannot
discover. Output is external, outside artifact/input parent directories, published exclusively and
atomically, never overwritten. Reads cap at 10 MiB/5,000 rows; field limits remain 250/64, artifacts
32 MiB. Invalid runs exit 2 with safe JSON categories, not raw/reference examples.

Before reference access, the evaluator verifies manifest pin/hash, dirty input, trusted artifact
hashes/sizes, canonical snapshot/policies, reconstructed pure dirty-only evidence, every mapping,
digest, review/resolution and both CSV projections. Only then does it read/verify reference hash,
tuple bijection, matching metadata and consistent field targets. Missing/duplicate/conflicting IDs,
JSON keys, mappings, unsupported policies, corrupt artifacts or unapproved effective values fail
closed; no partial join is silently scored. Unmapped historical decisions are refused. Pure backend
normalization/grouping/evidence may be imported, never app startup/config/provider/database code.

Production mode uses only `docs/flights-source-manifest.json` at its unchanged path. Explicit
`--synthetic-manifest PATH` requires synthetic=true, no upstream commit, the contract and declared
observed/reference hashes; results are labeled synthetic, never authentic benchmark performance.
Synthetic manifest shape (hash placeholders only):

```json
{"synthetic":true,"dataset_type":"raha_flights_v1","files":{"observed":{"sha256":"<dirty-sha256>"},"evaluation_reference":{"sha256":"<reference-sha256>"}}}
```

CSV spreadsheet escaping is reversed; JSON preserves exact identities. No input/artifact is rewritten.

## Metrics and limitations

Repair unit is `(job snapshot, tuple_id, time field)`; detection unit is `(job, raw flight, field)`.
One human decision can project to many cells. Accepted/overridden current values project onto their
mapped source cells; unapproved/stale/ungroupable cells retain dirty values **only in offline final-state
calculation**. Operational approved CSV columns stay empty; AI abstention/failure supplies no repair.

Primary **exact_string** uses decoded equality without trimming. Canonical-versus-formatted reference
differences still count. **conservative_semantic** uses unchanged parsed-clock policy/precision/qualifiers;
ambiguous/unsupported/missing context is unknown even when raw strings match. Approved canonical
clocks are already interpreted, not reparsed as raw ambiguous bare times. No context/seconds stripping.

Semantic original/reference and final/reference report equal/different/unknown for all cells. Repair
metrics use the **jointly scorable cohort** where original/reference, final/reference and original/final
comparisons are known; its original-error denominator can differ from pairwise different counts.
Report cohort size, overlapping exclusions and unscorable outcomes. Exact comparison scores every cell.

| Metric | Definition within its declared cohort |
|---|---|
| Corrected errors | Originally wrong, approved change, final equals reference |
| Harmful repairs | Originally valid, approved change, final differs from reference |
| Wrong-to-wrong | Originally wrong, approved change, final still wrong |
| Repair precision | Corrected errors / all approved changes, including harmful and wrong-to-wrong changes |
| Correction recall | Corrected errors / original errors in that cohort |
| Harmful-change rate | Harmful repairs / approved changes |
| Remaining errors | Final differs from reference, including unchanged unapproved errors |
| Coverage | Approved/unapproved cells / all time cells; approved fields and reviewed fields / groupable fields, separately |

Unchanged valid/errors, approved no-change cells and approved raw-string changes are separate counts.
All ratios expose numerator/denominator; zero denominator yields null, never 100%. Review states,
stale/ungroupable and no-candidate outcomes remain explicit. Frozen v1 manifests lack full AI lifecycle,
so not-requested/abstention/failure totals are unavailable/null, not inferred from missing links.

Detection compares the frozen `requires_attention` predicate with groups containing at least one
original/reference difference. Semantic negatives require all cells established equal; otherwise no
proven difference plus unknown cells makes the group unscorable. Report TP/FP/FN/TN and exclusions;
precision TP/(TP+FP), recall TP/(TP+FN), F1 2TP/(2TP+FP+FN). These are attention/group metrics, not
individual cell localization. Consensus can be wrong, producing false negatives.

Reports include versions, timestamps, hashes, alignment, policies/cohorts, states and limitations;
identical frozen inputs yield identical metric content except evaluated_at. They emit no individual
reference labels. Freeze worksets/proposals/decisions/configuration before labels; never tune detection
or normalization on answers. Future learning/tuning needs flight-level partitions, not related-source
row splits. Baseline/AI accuracy comparisons are not implemented by this reviewed-export evaluator.

A future separately authorized provider check should use one isolated eligible case, approved model,
privacy/retention terms and spending ceiling, no automatic retry, then record actual usage/latency,
reference-valid explanation and uncertainty or justified abstention. Measure valid grounded suggestions,
harmful-suggestion/abstention/failure rates and reviewer effort against a frozen deterministic baseline
on a preselected flight-separated set. One smoke test cannot prove an accuracy uplift. No clean values
or evaluation reports enter prompts. See [validation gates](VALIDATION.md).
