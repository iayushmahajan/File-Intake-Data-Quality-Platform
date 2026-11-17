# Bounded Flights AI investigation (Milestone 6)

AI investigation is optional, explicitly requested and non-authoritative. It can propose
one server-owned candidate or abstain. It cannot repair observations or approve a decision.
Deterministic evidence and its baseline work with no provider configuration or reference storage.
Human review, reconciled exports and evaluation remain deferred.

## API

For a completed `raha_flights_v1` job, first retrieve the existing discrepancy evidence.

- `POST /api/v1/flights/jobs/{job_id}/discrepancies/{discrepancy_id}/investigations`
  accepts exactly `expected_evidence_digest` (`sha256:` followed by 64 lowercase hex digits)
  and `request_id` (8–80 ASCII letters, digits, underscores or hyphens; a UUID is suitable).
- `GET` the same collection returns the latest investigation, or `not_requested`.
- `GET .../investigations/{investigation_id}` retrieves a stored outcome.

The server reconstructs evidence; clients cannot supply candidates or claims. An expected
snapshot mismatch is HTTP 409 before any provider request. The existing job/type/version,
completed-state, corruption and 5,000-observation projection guards also apply. Unknown
jobs/discrepancies/selected history IDs are 404; invalid input is 422; storage failure is
503 without private diagnostics. Global capacity exhaustion is 429 with Retry-After: 5.

Terminal operations return 200 with a truthful typed status; an existing running operation
returns 202. Lifecycle: `running` → `proposed`, `abstained`, `unavailable`,
`invalid_response`, `failed`, or `stale`. Preflight refusals are persisted as `ineligible`
or `unavailable`. `not_requested` exists only in the collection projection. An unavailable
provider or malformed response is never relabeled a model abstention. Every response has
`authoritative: false`. A stale history row retains its validated historical recommendation,
if any; `current: false` and `status: stale` prevent treating it as current. `stored_status`
shows the persisted state separately. GET recomputes freshness without writing. History is
also stale when the dataset can no longer be projected, or provider/prompt policy changes.

## Complete evidence and eligibility

Policies: `flight_investigation_v1`, `flight_investigation_prompt_v1`,
`flight_recommendation_v1`, plus existing detection and normalization versions.

Eligibility requires at least one supported candidate and confirmed conflict, ambiguous
claims, unsupported claims, or incomparable parsed precision/context. Supported agreement,
missingness alone, and cases without supported candidates are ineligible. These rules
are not tuned against reference labels.

One request contains the entire selected field: job/scope/digest/flight/field, policies,
status counts and orthogonal flags, all raw time claims and normalization reasons,
identity issue codes, all authorized candidates with precision/qualifiers, support counts,
supporting/confirmed contradicting/incomparable/context references, and internal source
inconsistency. Source IDs are stable job-scoped SHA-256 aliases, not trust scores or claims
of independence. Claim IDs hash discrepancy ID, evidence digest and original tuple ID.
The API maps these references back to stored observation/source IDs for current evidence.
No row is omitted or sampled. The baseline is deliberately omitted to reduce anchoring.

Excluded: other fields, full CSVs, filenames, arbitrary issue messages, credentials,
reference labels, evaluation results, and unrelated datasets. Time strings remain untrusted
source data, serialized as JSON in a user message separate from system instructions. The
system explicitly prohibits following embedded instructions. No tools, browsing, database
or filesystem access are provided to the model. This reduces injection risk; it cannot
prove that free-text reasoning is faithful. Output explanations remain untrusted plaintext;
a future UI must escape them rather than render HTML.

## Fixed budgets and provider setup

| Limit | Value |
|---|---:|
| Claims per selected field | 32 |
| Supported candidates | 8 |
| Bytes per raw time claim (UTF-8) | 160 |
| Complete serialized input, including instructions/schema | 32,000 UTF-8 bytes |
| Completion ceiling (including reasoning where supported) | 2,048 tokens |
| Received content accepted for validation | 16,384 UTF-8 bytes |
| Explanation / uncertainty | 1,200 / 800 characters |
| Supporting / contradicting citations | 16 / 16 |
| SDK transport timeout / total asynchronous request deadline | 20 / 30 seconds |
| SDK automatic retries | 0 |
| Reserved provider attempts per scope + digest + configuration | 3 |
| Global concurrent claimed requests | 2 |
| Claim lease | 90 seconds |

Any evidence budget excess refuses the whole request explicitly; it never cherry-picks a
subset. Bytes are a reproducible input bound, not an exact tokenizer estimate. Actual
prompt/completion/total token usage is saved when the provider reports it. There are no
estimated accuracy, confidence or cost figures. Validation bounds apply to returned content;
the transport still receives the provider response before validating its size.

Reuse existing settings, configured before process startup (placeholders only):

```dotenv
OPENAI_API_KEY=<local-secret>
OPENAI_BASE_URL=https://<openai-compatible-host>/v1
OPENAI_MODEL=<supported-chat-model>
```

No new dependency, settings subsystem or provider registry is introduced. URL credentials,
queries/fragments and invalid model identifiers are rejected, never stored. The legacy
transaction analytics implementation is unchanged. Reconciliation uses a separate narrow
`AsyncOpenAI` call with the same configuration conventions and bounded errors. The installed
SDK is `openai==2.54.0`. It exposes `max_completion_tokens`; official documentation describes
its reasoning-inclusive ceiling and configurable SDK timeouts/retries:
[Chat Completions create](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create),
[Python SDK](https://developers.openai.com/api/reference/python).

Plain JSON is requested in the prompt and strictly validated locally. Provider-specific
structured-output support is not assumed. No `response_format`, temperature, tool calls
or response repair/retry loop is used. A provider that rejects the request parameters
fails safely. Live provider/model compatibility has **not** been tested. This cost-incurring
endpoint is for the current local single-operator application; it must not be exposed
publicly without appropriate authentication/access controls. This milestone adds no auth.

## Output validation

Exactly six required fields, extra keys forbidden: `recommendation` (`propose`/`abstain`),
`candidate_id`, `supporting_claim_ids`, `contradicting_claim_ids`, `explanation`, `uncertainty`.
Strict types, nonblank bounded text, control-character checks, bounded unique references,
and duplicate JSON-key rejection apply. Proposals require exactly one current authorized
candidate and at least one supplied supporting claim that actually belongs to it. Every
contradicting citation must be a supplied, confirmed contradictory claim for that candidate.
Ambiguous/context claims cannot be cited as proven contradictions. Abstentions require a
null candidate and empty citation lists. No free-form time is accepted. Cross-field,
cross-snapshot, fabricated, repeated and wrongly attributed references fail validation.
This validates structural grounding, not the truth or entailment of generated prose.

Invalid JSON/schema/citations, truncation, refusal and oversized output are `invalid_response`.
Provider timeout is `failed/provider_timeout`; rate limits and provider API failures are
`unavailable`; unexpected SDK failures are `failed/provider_failure`. No raw exceptions,
prompts or unvalidated model text are saved in history or logged by this feature.

## Persistence, idempotency and failure recovery

Additive migration `0005` creates only `flight_investigations`, with a foreign key to the
existing job. Original data, job behavior and previous migrations are unchanged. All new
fields belong to new rows: no backfill, historical reclassification or new defaults on old
tables. Nullable provider/result/usage-related data support failures before a provider call;
usage is an explicit empty JSON object until reported. Creation timestamps and policy
versions are always recorded. There is no human decision state.

Each row stores scope, expected digest, provider/model/configuration fingerprint, policy
versions, request identity, attempt number, claim token/lease/slot, status/error category,
validated recommendation/citations, safe response model/ID, usage, timestamps and an input
payload SHA-256/byte count. It does not store full prompts or raw provider responses.

Database constraints enforce globally unique request IDs, unique occupied nullable slots,
one running row per job/discrepancy, and unique charged attempt ordinal per evidence/config.
Short transactions reserve ownership and publish results; no transaction spans the await.
A conditional update publishes only with the still-valid token and unexpired lease. Evidence
and configuration are rebuilt/checked after provider completion. Stale results are historical
only. A storage failure cannot manufacture a successful outcome; refresh/retry the same key.

Replay of a bound request ID returns its existing row, including failure, without calling
again. Successful proposals and genuine abstentions are cached per evidence/configuration;
a fresh request may return the existing result and its original request ID. Cache hits and
requests that encounter an existing running claim do **not** create alias request rows;
only the returned stored `request_id` is durably bound. Reuse of an already bound key for
another scope/digest is 409. Explicit retry after failure uses a new request ID and consumes
one of at most three reservations. Crash-before-send still consumes an attempt conservatively. A post-claim cache recheck
closes the completion-versus-reservation race; if it finds an earlier completed result,
the new row retains that validated result/response identity without another provider call
or duplicated usage counters. That already reserved ordinal is conservatively consumed.
Changing model/policy constitutes a different configuration budget.

Expired running claims appear `failed/interrupted` on GET without writing; a later POST
reaps expired claims, frees capacity and may reserve a new attempt. There is no automatic
retry or second queue. Cancellation/disconnection can leave a pending row until its lease
expires; the client polls the stored ID or latest endpoint. A late worker cannot publish
with an expired/superseded claim. Database uniqueness controls overlapping application
processes, but actual PostgreSQL contention/locking remains unverified. A timeout/crash can
leave uncertainty about whether a provider billed a request: this is not exactly-once external
execution. New explicit retries can incur additional charges within the reservation budget.

## Rollout and verification

Migration tests upgrade disposable SQLite state from `0004` and check preserved observations,
legacy metadata, indexes, request uniqueness and foreign keys. Do not start the normal API
against development storage: its lifespan automatically migrates. Applying `0005` to the
real database requires a reviewed backup of PostgreSQL and existing source/output storage,
verified restore procedure and separate rollout approval. No existing development migration
was applied. Live PostgreSQL, Redis, Celery and provider operation remain unverified.
Destructive downgrade is disabled, consistent with prior migrations: restoring an approved
backup loses newer history unless it is separately retained/exported. Retain the AI history
with its parent jobs; no automatic deletion or cascade is added.

Tests use synthetic observations, fake SDK/provider responses, temporary databases/files,
and the existing memory broker. Focused command:

```bash
timeout 120s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests/test_flight_investigations.py -q
```

Milestone 7 may reference a current investigation ID, evidence digest, validated candidate ID
and supplied claim IDs, together with deterministic evidence. It must implement separate,
authoritative human decisions. Neither a baseline nor an AI proposal constitutes approval.
