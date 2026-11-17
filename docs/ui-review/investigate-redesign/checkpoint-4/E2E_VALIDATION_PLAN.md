# Controlled AI and persisted-workflow validation — proposed, not executed

This plan requires separate authorization. Checkpoint 4 performs only read-only live inspection and synthetic write-path UI tests. Do not run these future writes against dataset 5 or any of the five existing imports.

## Preconditions and isolation gate

1. Review a dedicated disposable runtime configuration before creating resources. It must use fresh PostgreSQL, Redis and application-file volumes, a distinct Compose project/network, verified free localhost ports, a distinct queue and matching exact CORS origins. Mount neither `reconcile-workbench` nor `file-intake-processing-service` storage. Do not mount benchmark directories, evaluation references or the Docker socket. Do not attach to either existing project's network.
2. `compose.reconcile.yaml` currently declares `name: reconcile-workbench`; `scripts/reconcile.sh` explicitly uses `-p reconcile-workbench`. Do not run that launcher to create the validation stack or assume changing an environment variable isolates it. Prepare a reviewed, separately scoped configuration/invocation and inspect its resolved volume, network, connection and port identities first. No such disposable write-test runtime has been verified in this checkpoint.
3. Confirm the isolated database identity and expected migration head before startup; normal API startup applies migrations. Only its fresh database may be migrated. Record baseline fingerprints/counts for both protected projects; their resources must remain untouched. Resource creation, provider configuration and eventual stopping of the validation runtime each remain within the future authorization; no broad cleanup or volume removal is implied.
4. Import a SHA-256-verified copy of the pinned **dirty** benchmark into that isolated runtime only, after approval for that import. Keep its local-research rights caveat. Never copy any existing stored job or review records by modifying production/development tables. Use the new job's ID in every subsequent operation.
5. Approve a provider/model and a spending ceiling before supplying credentials. Use local, ignored, permission-restricted secrets. Explicitly configure `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `OPENAI_MODEL` for the isolated API; never print their secret values. The existing Compose configuration intentionally sets the key to an empty string, so adding a host environment key alone does not configure it. Any override/recreation belongs only to the future disposable environment, not the running project.

## Stage A — one genuine AI investigation

Choose one eligible conflict/uncertain case using **dirty-only** findings before consulting any reference. Save its case ID, digest, candidate IDs and deterministic baseline proposal/abstention. Demonstrate that the actual provider receives only the current bounded field evidence, returns a strictly validated candidate or abstention, and that explanation/uncertainty/citations can be reloaded. A successful proposal does not demonstrate correctness; a truthful abstention or provider failure is also a meaningful observed outcome.

Authorize **one explicit provider request initially**, with no automatic retry or batch. Current implementation limits (`backend/app/reconciliation/ai.py`, `docs/FLIGHTS_AI.md`): 32 claims, 8 candidates, 32,000 input bytes, 2,048 completion tokens, 16,384 returned content bytes; SDK retries 0, 20-second transport timeout and 30-second total deadline. The server permits up to 3 explicitly reserved attempts per case/digest/configuration and 2 concurrent requests; these are ceilings, not permission to use them. Stay serial and stop after the first result or failure. Do not click retry after an uncertain response without checking the existing request identity and persisted status.

Check current official provider pricing and retention/privacy terms at the time of authorization; no cost estimate is asserted here. Set a provider-side budget where available and record actual reported token usage, latency and safe failure category. Bytes are not exact token counts. Check API parameter compatibility with the approved model: real provider compatibility remains unverified. Keep the local cost-incurring endpoint private; this application has no production authentication.

The AI must never receive `clean.csv`, dirty/reference comparisons, evaluation reports or independently corrected examples. No reference path enters runtime settings, containers, frontend fixtures or provider payloads. Review evidence remains untrusted text and AI explanations remain escaped text. Strict reference allowlisting does not prove the factual truth of every generated sentence.

## Stage B — explicit human review and history

| Step | Existing capability / expected result |
|---|---|
| Evidence-supported judgment | Select a current supported candidate through the existing `override` action, provide reviewer attribution and rationale, and submit expected digest/revision plus a unique request ID. If Stage A actually produced a current valid proposal, accepting it is an alternative, not a prerequisite. No candidate is pre-approved by majority support. |
| Legitimate unresolved outcome | Choose a different case with insufficient evidence, submit `unresolved` with an explanation and no effective value. Do not force a correction to complete a review. |
| Persistence | Reload the browser and retrieve current review and chronological history in new API requests. Check event IDs, monotonic revisions, candidate/manual origin and original request identities. Repeating an exact request is idempotent; do not generate a different ID merely to retry an uncertain write. |
| Freshness / conflicts | Existing synthetic tests cover stale digest/revision, invalid manual values, conflicting idempotency payloads and unknown write outcomes. An isolated backend check may verify these with approved requests; do not corrupt observations to manufacture a stale case. |

Current attribution is an unverified local name/label. The API does not store a separate independently verified correction state. Additional authoritative information can be explained in rationale; do not invent a verification badge or claim the benchmark establishes historical truth.

## Stage C — frozen export and immutability

1. Read the current export snapshot digest and explicitly acknowledge conservative unresolved handling in History. Create one frozen export using that digest and its own request ID.
2. Retrieve metadata and download the reviewed CSV, exceptions CSV and provenance JSON through existing safe endpoints. Verify every artifact byte length and SHA-256 against metadata; preserve these exact files outside application storage as evaluation inputs.
3. Confirm the chosen accepted/overridden value appears with its actual review status; rejected, unresolved and unreviewed fields stay empty as authoritative values and appear in exceptions. Trace each field through decision/event revision, evidence digest and `(job, tuple_id, field)` observation-cell mappings. A manual replacement, if separately tested, must be labeled a human assertion without invented source support.
4. Compare the isolated import's input hash, observation count and ordered complete observation fingerprint before/after all writes. Source evidence must match exactly; only investigation/review/export tables and new owned artifacts may change. Confirm protected-project fingerprints and container identities also remain unchanged.
5. Reopen/download the same frozen export in a new session and verify hashes. A stronger later-decision test may be separately authorized: append one new review revision, then prove the existing export remains byte-identical. Do not silently expand the initial two-decision/one-export run to include extra revisions or exports.

## Stage D — offline comparison, after freeze

Only after proposals, decisions and artifacts are frozen may a separate offline process receive the explicit reference path. Follow `docs/FLIGHTS_EVALUATION.md` and the existing file-only `scripts/evaluate_flights.py` entry point with `--export-dir`, `--metadata`, `--dirty`, `--reference` and `--output`. Keep inputs/results outside the repository, runtime mounts and `DATA_DIR`. Verify pinned reference integrity in that offline process, not in the application. Do not feed its results back into prompts, suggestions, review decisions or baseline thresholds for the same frozen run.

The evaluator already supports integrity checks and aggregate metrics for **reviewed exports**. This does not directly score unapproved AI proposals or baseline suggestions. A separate small offline analysis would be needed to compare those frozen outputs using the same units and an explicit missing/ambiguous-reference policy. Do not add it during this checkpoint or equate its cell-level denominator with a case-level rate.

## Separately scoped assessment of AI usefulness

After the single-call smoke test, preselect a small flight-separated set using dirty evidence only, with conflicts and uncertainty represented. Compare frozen deterministic baseline proposals/abstentions with validated AI proposals/abstentions on identical evidence. Keep AI failures distinct from abstentions. For reviewer-effort comparisons, use comparable tasks and counterbalance which cases show AI; reviewing the same case twice introduces learning bias.

Proposed measurements (not measured here):

- Valid grounded output rate, citation errors, abstention and provider-failure rates; count eligible requested cases separately from all flagged cases.
- Correct versus harmful/incorrect proposed selections against an isolated, adequate reference; proposal coverage uses all eligible requested cases, accuracy among proposals uses only evaluable proposals. State exclusions explicitly.
- Deterministic-baseline comparison on the same cases, including cases where either method abstains; no cherry-picking only successful AI answers.
- Reviewer time, source-record expansions and subjective explanation usefulness under comparable conditions; instrumenting these is not currently implemented. Human acceptance alone is not evidence of correctness.
- Actual usage, latency and spend reported by the provider; do not invent confidence probabilities or precise costs from source agreement.

Existing capabilities cover bounded provider execution, typed results, human actions/history, frozen artifacts and offline export evaluation. Missing prerequisites are approved isolated runtime/credentials/spend, a genuine provider compatibility test, a controlled study protocol and any direct AI-versus-baseline scoring/effort instrumentation. Do not expand backend schemas or the UI to obtain a marketing metric.

## Completion record for the future authorized run

Report isolated resource identities, selected job/cases/digests, request IDs and outcomes, safe provider metadata/usage, decision revisions, artifact hashes and read-only before/after evidence checks. Report failures truthfully and keep aggregate evaluation separate from operational outputs. Stop on any isolation failure. This document neither authorizes nor executes that run.
