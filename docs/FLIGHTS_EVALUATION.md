# Offline Flights evaluation — Milestone 8

Entry point: `scripts/evaluate_flights.py`; policies `flight_offline_evaluation_v1` and evaluator
`1.0.0`. There is no evaluation API, database model, startup hook, worker, provider request,
training or threshold tuning. Evaluation does not confer ground truth or approve repairs.

## Inputs and invocation

Save the already published export-detail response as a trusted local `metadata.json`, and
obtain its unchanged `reviewed.csv`, `exceptions.csv` and `provenance.json` artifacts. The
command consumes files only; it never downloads from application endpoints or reads a DB.
Metadata is the trust anchor for artifact hashes, not a cryptographic signature or authenticated
proof of who reviewed data. Keep these export inputs unchanged.

```bash
python3 -B scripts/evaluate_flights.py \
  --export-dir /external/frozen-export \
  --metadata /external/export-metadata/metadata.json \
  --dirty /external/benchmark/observed/dirty.csv \
  --reference /external/benchmark/reference/clean.csv \
  --output /external/evaluation-results/run-001.json
```

Replace all `/external/...` placeholders with explicitly chosen local paths. The reference
argument has no default. Dirty/reference inputs must be regular, non-symlink files outside
the repository and exported `DATA_DIR`, if configured. They must not live in application
storage or Docker mounts; nonstandard runtime mounts cannot be discovered by a standalone
file-only process, so the operator must keep them separate. Output must also be external,
outside runtime `DATA_DIR`, and outside the artifact and input-file parent directories.
Output publication is exclusive and atomic: a complete flushed temporary file is hard-linked
to the chosen report name; an existing report is never overwritten. No individual reference
answers or corrected record examples appear in the aggregate report or CLI summary.

Production mode uses the authoritative local `docs/flights-source-manifest.json`, including
commit `7be1334b8c7bbdac3f47ef514fb3e1e8c5fc181c` and both recorded SHA-256 hashes. The
observed file hash must also match the frozen export input hash. Do not alter that manifest
to evaluate another dataset. A deliberately separate `--synthetic-manifest PATH` mode requires
`synthetic: true`, no upstream commit, dataset type and explicit observed/reference hashes:

```json
{"synthetic":true,"dataset_type":"raha_flights_v1","files":{"observed":{"sha256":"<synthetic-dirty-sha256>"},"evaluation_reference":{"sha256":"<synthetic-reference-sha256>"}}}
```

Synthetic reports are labeled `benchmark.kind: synthetic`; they cannot stand in for pinned
benchmark performance. Real benchmark copies were absent at M8 inspection. No authentic frozen
reviewed benchmark export was supplied, so no real benchmark performance was generated and
no reacquisition was needed. When such an export exists, reacquire only the commit-pinned
files if necessary, verify hashes, and retain local-research-only restrictions from
`FLIGHTS_BENCHMARK.md`. Third-party redistribution/demo rights remain unresolved.

## Execution boundary and integrity

1. Read source/version metadata and verify dirty bytes/header, bounded rows and unique IDs.
2. Verify published metadata and all three artifact hashes/sizes (32 MiB combined ceiling).
3. Verify snapshot digest using canonical UTF-8 JSON, policies, IDs, timestamps and schemas.
4. Reconstruct dirty-only groups/evidence using unchanged pure reconciliation functions.
5. Check every field digest, source/tuple/position mapping, decision and approved resolution.
6. Cross-check reviewed and exceptions CSVs against the validated provenance projection.
7. **Only now** open the explicit reference; verify its hash and tuple-ID bijection, exact
   source/flight identities and raw reference consistency per nonblank flight/field.
8. Compute aggregate comparisons/metrics and publish only an evaluation-owned report.

The shared `inspect_flights.decode_flights()` helper handles seven-column CSV decoding.
The existing `read_flights(path)` remains backward compatible. A narrow offline adapter
reconstructs v1 intake identity issues, including exact issue codes/messages/positions, to
verify the frozen evidence digest. Backend interoperability tests cover actual generated
exports with blank/malformed identities, flagged sources and escaped observation identifiers.
No operational parser, provider, database, configuration or application-startup module is
imported: only pure normalization/grouping/evidence modules are reused. Runtime code has no
imports of this evaluator. A subprocess import guard verifies that boundary.

Validation fails closed on missing/modified artifacts, duplicate JSON keys, unsupported
policies, wrong dataset hashes, missing/duplicate IDs, mismatched identities, inconsistent
reference targets, repeated/conflicting mappings, invalid decision/revision/provenance, and
unapproved effective values. No rows are quietly skipped. Current v1 evaluation refuses
unmapped historical decisions rather than guessing how a different scope/policy maps.
CLI failures return exit 2 with safe JSON error categories, without source/reference values.
Trusted-hash consistency does not independently authenticate historical AI execution: the
export freezes human events and references, not complete AI provider history.

CSV headers/widths and complete row inventories are checked. Protective leading apostrophes
are reversed under the M7 presentation policy; JSON provides exact identities. Source data,
reviews and artifacts are never rewritten. Source/reference reads cap at 10 MiB/5,000 rows;
complete field reconstruction retains the existing 250-claim and 64-candidate limits.

## Units and comparison policies

**Repair cell:** `(job snapshot, tuple_id, time field)`. Every observation has four cells.
**Detection group:** `(job snapshot, raw flight, field)`, for groupable observations only.
**Decision:** one explicit reviewer action, potentially projected to multiple source cells.
These are separate denominators.

An approved current accepted/overridden value is projected onto every listed observation
cell for that field. All unapproved/stale/ungroupable cells retain the dirty value **only in
the offline final-state calculation**. Operational approved-value CSV columns remain empty.

- **exact_string:** decoded string equality, with no trimming/normalization. Approved canonical
  clock strings may differ from correctly formatted reference strings; such differences still
  count as exact errors. This primary benchmark policy can penalize presentation changes.
- **conservative_semantic:** the existing v1 normalizer establishes parsed-clock equality or
  difference only for compatible precision, qualifiers and policy. Missing, placeholder,
  ambiguous and unsupported comparisons remain unknown, even for identical unsupported text.
  Already approved canonical clocks are interpreted canonical values, not reparsed as raw
  ambiguous AM/PM-free input. No seconds truncation, context stripping or new grammar occurs.

Semantic `original_reference` and `final_reference` each report equal/different/unknown counts
across all cells. Repair categories use a **jointly scorable cohort** requiring known
original/reference, final/reference and original/final comparisons. Therefore semantic
`counts.original_errors` may differ from `original_reference.different`; the former is the
joint-cohort denominator. Outcome-scorable/unscorable totals and overlapping exclusion reasons
are explicit, including incompatible precision/qualifiers. Exact comparison scores all cells.

## Metric definitions

Let O, F and R be original, projected final and reference values under the declared policy.
Let changed mean an approved O→F change under that policy. All repair counts below use the
policy's jointly scorable cohort.

| Count/metric | Definition / denominator |
|---|---|
| Original errors / originally valid | O differs from R / O equals R |
| Approved changes | Approved cells with O different from F |
| Corrected errors | Originally wrong, changed, F equals R |
| Harmful repairs | Originally valid, changed, F differs from R |
| Wrong-to-wrong changes | Originally wrong, changed, F still differs from R |
| Unchanged valid cells | Originally valid and F still equals R |
| Remaining errors | F differs from R, including retained unapproved errors |
| Unchanged original errors | Originally wrong with no established change |
| Approved no-change cells | Approved value equivalent to O under this policy |
| Repair precision | Corrected errors / all approved changes; harmful and wrong-to-wrong changes remain in the denominator |
| Correction recall | Corrected errors / original errors in the same cohort |
| Harmful-change rate | Harmful repairs / approved changes |
| Approved/unapproved cell coverage | Corresponding cells / all original time cells, including ungroupable observations |
| Approved field coverage | Accepted + overridden fields / groupable fields |
| Current reviewed field coverage | Accepted + overridden + rejected + unresolved / groupable fields |

Every ratio includes numerator, denominator and value. A zero denominator produces JSON null,
never 100%. `approved_raw_string_changes` separately reports raw changed approved cells even
when semantic changes/outcomes cannot be established.

Detection predicts the **unchanged pre-existing** `FieldEvidence.requires_attention` predicate.
Reference-positive groups contain at least one original/reference difference. A semantic
negative requires all its cells to be established equal; if none is proven different and
some are unknown, the group is unscorable. Exact groups are always scorable. Report TP/FP/FN/TN,
excluded groups, precision TP/(TP+FP), recall TP/(TP+FN), F1 2TP/(2TP+FP+FN).

These are attention-queue/group metrics, not individual error localization. The queue deliberately
flags uncertainty and missingness too. Consensus can still be wrong: fully agreeing but incorrect
observations can produce false negatives. No predicate/threshold was changed after reference access.

Field and cell counts distinguish unreviewed, accepted, overridden, rejected, unresolved, stale
and ungroupable cases. No-candidate counts are reconstructed from verified deterministic evidence.
Complete AI lifecycle is absent from frozen v1 manifests: not-requested, genuine abstention and
provider failure counts are explicitly unavailable/null, not inferred from missing links.
Baseline/AI diagnostic policy comparisons are deferred; they do not fill unapproved fields.

## Output, reproducibility and verification

One JSON report contains policy/evaluator versions, invocation timestamp, source commit/manifest
hash, input hashes/metadata, export identity/artifact hashes, alignment, both comparison policies,
coverage/states and limitations. No individual reference labels are emitted. Identical frozen
inputs yield identical metric content; `evaluated_at` intentionally varies. The callable supports
a fixed timestamp for reproducibility tests; CLI output paths are not part of report content.

```bash
python3 -B -m unittest discover -s scripts -p test_flights_evaluation.py -q
python3 -B -m unittest discover -s scripts -p test_flights_benchmark.py -q
timeout 120s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests/test_flights_offline_evaluation.py backend/tests/test_flight_review_exports.py backend/tests/test_flights_evidence.py -q
timeout 180s env PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m pytest -p no:cacheprovider backend/tests -q
git diff --check
```

No operational stabilization defect requiring a runtime change was found. Intake dispatch,
job-kind routing, fenced publication, immutable observations, evidence IDs, AI freshness,
review revisions and export publication remain covered by their existing regressions.
No new migration was introduced. One concrete verification gap was closed: the backend CI
job now also runs the standalone benchmark/evaluation unittest suites. Previously its pytest
command did not collect these script-level metric tests. Existing CI jobs are preserved.

## PostgreSQL verification gate — not executed

No authorized disposable PostgreSQL environment was provided; `psql` was unavailable. Existing
`scripts/verify_async_stack.py` creates/rebuilds Docker services and later removes volumes, so
it was deliberately not run. SQLite results are not PostgreSQL verification. The actual dev
revision, backup ownership and restore procedure remain unknown and separate rollout gates.

Reviewed risks:

| Area | Required PostgreSQL evidence |
|---|---|
| 0004 adoption | Historical `transactions` default/backfill, nullable SHA, JSON `issues` default `'[]'`, text encoding/NUL handling |
| FK/check/indexes | Real foreign keys, unique tuple/position keys, positive review revisions/actions, globally unique request IDs |
| Index sizes | Tuple IDs capped at 1,024 UTF-8 bytes; scoped SHA IDs/request lengths bounded; verify real B-tree limits/encoding |
| 0005 claims | Nullable unique slots allow terminal rows; partial indexes enforce one running scope and unique charged ordinal; parallel conflicts roll back safely |
| JSON | SQL NULL versus JSON null both decode appropriately; assignments persist entire validated dictionaries; no JSON equality-index assumptions |
| Reviews/exports | `SELECT FOR UPDATE` serializes final snapshot checks/commits against decision writes, with no lost revision or duplicate key |
| Isolation | READ COMMITTED single-statement latest-revision vector; no hidden REPEATABLE READ stale snapshots; inspect actual server settings |
| Failures | Lock timeout/deadlock rollback, connection loss/ambiguous acknowledgement, no long provider transaction |
| Files/DB | Unique complete files before metadata; stale cleanup and commit-ambiguity orphan retention; database and files backed up together |

Future procedure, only after separate authorization:

1. Provision a **new disposable PostgreSQL cluster** with a dedicated scratch database/role,
   separate port/socket, no development volumes/mounts/remotes, no production credentials.
   Record its identity and disposable ownership. Install no packages/start no services as part
   of this milestone. Set `M8_DISPOSABLE_DATABASE_URL` to this explicitly verified scratch URL.
2. From a clean subprocess, run this guarded migration probe; it does not use application startup:

```python
# Run with backend/.venv/bin/python and PYTHONPATH=backend, after provisioning approval.
import os
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
url = os.environ["M8_DISPOSABLE_DATABASE_URL"]  # Never fall back to DATABASE_URL.
engine = create_engine(url)
with engine.begin() as connection:
    name, user, address, port = connection.execute(text(
        "SELECT current_database(), current_user, inet_server_addr(), inet_server_port()"
    )).one()
    assert name.startswith("reconcile_m8_test_")
    assert user.startswith("reconcile_m8_test_")
    assert not connection.execute(text(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
    )).scalar()  # Require newly empty scratch database.
    config = Config(str(Path("backend/alembic.ini").resolve()))
    config.attributes["connection"] = connection
    command.upgrade(config, "0003")
    # Seed synthetic legacy jobs/analytics/records and store their row hashes here.
    command.upgrade(config, "0004")
    command.upgrade(config, "0005")
    command.upgrade(config, "0006")
    assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0006"
```

3. Before accepting PostgreSQL readiness, extend the disposable probe with the synthetic seed
   and preservation assertions from `backend/tests/test_migrations.py`,
   `test_flight_investigations.py` and `test_flight_review_exports.py`. Use that explicit engine,
   not the normal test conftest: **conftest deliberately overrides DATABASE_URL to SQLite**.
   Changing an environment variable alone does not convert existing tests into PG tests.
4. With two independent connections, seed one completed synthetic Flights job. Connection A:
   `BEGIN; SELECT id FROM processing_jobs WHERE id=:job FOR UPDATE;`. Connection B:
   `BEGIN; SET LOCAL lock_timeout='500ms';` then the same lock must time out; roll B back.
   After A commits, B must acquire the lock. Repeat with actual review/export functions in
   subprocesses pointed only at the guarded scratch engine: exactly one stale-revision request
   succeeds; identical request retries return one event; export commits a coherent old vector
   before a waiting review or rejects a vector changed before locking.
5. Race 3+ synthetic AI reservations with a fake provider and no API key/network: at most two
   slots, one active scope, at most three ordinals; stale tokens cannot publish. Exercise FK,
   duplicate key, JSON null, provider-outside-transaction and rollback cases. Run worker
   duplicate-delivery/lease cases against only that scratch DB; Redis/Celery remains a separate
   explicitly isolated transport verification. No normal application launcher is needed.
6. Verify file publication failure and ambiguous commit behavior in a scratch DATA_DIR. Capture
   logs without credentials. Retire only the resources documented as scratch and explicitly
   authorized for teardown. Never run the development Compose cleanup command.

The migration probe above alone is **not** a completed concurrency/preservation test suite.
Live rollout needs verified backup+restore of PostgreSQL and source/output storage, actual
revision inspection, reviewed sequential `0004`–`0006` upgrade, and approval before launching
an app whose lifespan auto-migrates. Destructive downgrades remain disabled. No development
migration, backup, service operation, teardown or provider request was performed here.

## Frontend readiness

Flights intake/status/observations, discrepancies, explicit AI investigation, human review/history
and frozen exports retain their existing typed APIs. Frontend clients must distinguish upload
acceptance from completion, AI failure from abstention, stale history from current approval,
and rejected/unreviewed values from approved resolutions. Refresh after 409; handle 413/422/503.
Existing error details include strings, intake objects and Pydantic validation lists; normalize
those in the API client without breaking backend contracts. Evaluation remains offline JSON;
no public metrics/import endpoint was added for the future History page. Authentication/live
provider and PostgreSQL verification remain separate deployment gates, not frontend redesign work.
