# Flights benchmark foundation — Milestone 2

This is an offline benchmark foundation, not application intake or reconciliation.
The machine-readable [source manifest](flights-source-manifest.json) pins the bytes,
retrieval date, hashes, URLs, and licensing uncertainty. Real CSVs are local-only.

## Provenance and use limitations

Source: [BigDaMa/raha](https://github.com/BigDaMa/raha), commit
`7be1334b8c7bbdac3f47ef514fb3e1e8c5fc181c` (2025-06-05). The latest
Flights-directory change at that pin is `82f3323c02f32b1154342d76cbcd3cdeb2233914`
(2019-11-07). Retrieved 2026-11-11 through the GitHub connector because shell DNS
was unavailable. Saved bytes match upstream Git blob SHA-1 identities as well as
the recorded SHA-256 hashes; CRLF line endings were preserved.

The pinned root LICENSE.md declares Apache-2.0 for the project. The Flights
directory contains only dirty.csv and clean.csv: no dataset-specific license,
NOTICE, collection description, or third-party permissions statement was found
there. Repository notice discovery found no separate dataset rights declaration.
This does not establish that the project can grant every underlying data right.

Research provenance:

- Mahdavi et al., **Raha: A Configuration-Free Error Detection System**, SIGMOD
  2019, pp. 865–882, [DOI](https://doi.org/10.1145/3299869.3324956).
- Mahdavi and Abedjan, **Baran: Effective Error Correction via a Unified Context
  Representation and Transfer Learning**, PVLDB 13(11), 2020, pp. 1948–1961,
  [paper](https://www.vldb.org/pvldb/vol13/p1948-mahdavi.pdf).
  Section 6.1/Table 2 identifies Flights as a reused benchmark and cites Li et al.
  and HoloClean; it documents the four flight-to-time dependencies.
- Li et al., **Truth Finding on the Deep Web: Is the Problem Solved?**, identified
  as VLDB 2013 in the [authors' arXiv record](https://arxiv.org/abs/1503.00303).
  It studies conflicting web sources in the Flight domain. This is a research
  lineage, not a verified byte-level derivation of this particular CSV subset.
- HoloClean: Rekatsinas et al., PVLDB 10(11), 2017, pp. 1190–1201, as cited by
  Baran. Original collection permissions, subset transformations, and independent
  verification of reference labels remain unresolved.

Conservative project policy: retain the acquired copies for local research;
do not commit raw files, publish reference answers, redistribute them, or bundle
them into public demos. Use synthetic observations for screenshots and public
demos pending a separate rights review. Public availability and the paper's own
license are not evidence of underlying dataset clearance. This records uncertainty,
not a legal determination that local or public use is authorized.

## Storage and commands

Choose an explicit absolute `FLIGHTS_BENCHMARK_ROOT` outside this repository.
Do not use backend/data, a Docker bind mount, a served directory, or DATA_DIR.
This shell variable is only a command convenience; it is not an application setting.

```text
<external benchmark root>/
  observed/dirty.csv
  reference/clean.csv
```

Use a private directory (0700) and files (0600). Temporary storage is acceptable
for inspection but can disappear; reacquire exact pinned bytes and verify hashes
before later use. No developer-specific path is required or committed.

With the root explicitly selected, acquisition can use each manifest URL:

```bash
umask 077
mkdir -p "$FLIGHTS_BENCHMARK_ROOT/observed" "$FLIGHTS_BENCHMARK_ROOT/reference"
# Retrieve exactly the two commit-pinned URLs in flights-source-manifest.json.
# Verify their bytes and SHA-256 against that manifest before use.
python3 -B scripts/inspect_flights.py --benchmark-root "$FLIGHTS_BENCHMARK_ROOT"
```

The dirty command opens only `observed/dirty.csv`, never scans the root, and has no
reference argument/default. It rejects repository-local roots and symlink file or
directory redirection. Its JSON includes complete dirty-only per-flight raw-value
counts, per-flight/per-source observation counts, and format-shape histograms.
Keep any redirected dirty report beside observed data, outside the repository.

The separate evaluation-only integrity command requires an explicit reference:

```bash
python3 -B scripts/inspect_flights_reference.py \
  --benchmark-root "$FLIGHTS_BENCHMARK_ROOT" \
  --reference "$FLIGHTS_BENCHMARK_ROOT/reference/clean.csv"
```

It rejects repository-local/misplaced/symlinked references and emits aggregates
only. Keep redirected alignment output in the external reference directory.
It is an integrity inspection, not a completed evaluator or a repair algorithm.
The future evaluator must independently require frozen outputs before reading labels.

Neither script imports FastAPI, settings, workers, database code, or application
startup. Dependency direction is reference inspector → explicit-file reader in
dirty inspector; dirty inspector never imports reference inspection. Scripts are
outside the backend Docker build context. No runtime settings or mounts changed.
The root is outside the configured repository bind mount. Tests enforce the
current runtime import boundary and Git exclusions for accidental CSV copies.

This is a code/execution boundary, not an OS sandbox against a user deliberately
copying/relabeling a file or uploading it manually. Do not provide the reference
path or file to the application. Future operational processing must continue to
work when the entire reference directory is absent. Do not import these offline
inspection scripts into production modules.

## Verified dirty-data findings

Exact header/order (all values remain strings):

```text
tuple_id,src,flight,sched_dep_time,act_dep_time,sched_arr_time,act_arr_time
```

There are 2,376 rows, 2,376 distinct nonblank tuple IDs, 100 distinct flight keys,
and 38 distinct source strings. No missing/duplicate tuple IDs, blank source/flight
keys, whitespace-only cells, UTF-8 errors, or CSV structure errors were found.
All flight keys match the descriptive shape `[A-Z0-9]{2,3}-[0-9]+-[A-Z]{3}-[A-Z]{3}`;
this is not airline identity validation. Each flight has 17–29 observations and
distinct sources; each source supplies 1–100 observations. There are no repeated
`(flight, src)` pairs in these bytes. Synthetic tests nevertheless cover them.
Whitespace is inspected only to classify blank identities/cells, not to merge raw
keys or values. Distinct source IDs do not prove statistical independence: source
copying or shared upstream feeds are not established by these files.

| Time field | Empty strings | Groups with >1 nonempty raw value | Groups with >1 raw value including empty | Groups mixing empty/nonempty |
|---|---:|---:|---:|---:|
| sched_dep_time | 784 | 68 | 98 | 98 |
| act_dep_time | 376 | 100 | 100 | 92 |
| sched_arr_time | 770 | 87 | 100 | 98 |
| act_arr_time | 382 | 100 | 100 | 88 |

There are 9,504 time cells, including 2,370 empty strings. Across 400 possible
flight/field groups, 355 contain multiple distinct nonempty raw strings; 398
contain multiple strings if empty is included. These are raw disagreements,
not proven errors, normalized conflicts, candidate choices, or accuracy scores.

Dirty format categories include dotted 12-hour meridiems; bare colon times;
numeric dates before a time; month/day annotations; weekday prefixes; compact
meridiem/date forms; noon; relative offsets; estimated/runway/delay/on-time text;
HTML-like `&nbsp`; trailing markers; and `Not Available` / `Contact Airline` text.
These placeholders remain literal values, not empty strings. The script's shape
histogram replaces digit runs with `N` for description only: it never changes raw
counts or rows. Date annotations already present must be preserved; do not infer
a year, service date, locale, timezone, or UTC offset from an ambiguous annotation.

## Evaluation-only integrity findings

The reference has the same header, 2,376 rows and unique nonblank tuple IDs.
All 2,376 IDs join one-to-one; neither side has unmatched keys. Matched src and
flight strings agree exactly. Row order also happens to match, but is not the
alignment contract. Use dataset hash + tuple_id + field, not row position.

All four observation fields align. No empty/whitespace reference cells or
contradictory nonempty reference values within a flight/field were found; no
reference group mixes empty/nonempty. Thus one reference value per flight/field
is supported for these pinned bytes. This does not certify real-world truth.

| Field | Exact dirty/reference differing cells |
|---|---:|
| sched_dep_time | 911 |
| act_dep_time | 1,558 |
| sched_arr_time | 1,100 |
| act_arr_time | 1,351 |
| tuple_id / src / flight | 0 / 0 / 0 |
| Four-time-field total | 4,920 |

The historical 2,376 / 100 / 38 / 4,920 hypotheses are verified for this pin only.
The 4,920 count uses exact decoded strings over the 9,504 time cells, joined by
tuple_id; including the three metadata columns changes neither numerator nor
differences, but gives a different denominator (16,632 cells). No normalization
was applied and no model/baseline performance was measured.

## Proposed application contract, not implemented

Contract identifier `raha_flights_v1`, version 1; exactly the seven fields above
in that order, UTF-8 with optional BOM, valid quoted CSV. Support these benchmark
bytes first; no arbitrary schema registry or configurable industry framework.

- **Observation identity:** dataset/import snapshot plus opaque raw tuple_id;
  preserve logical CSV row number separately. Require nonblank unique IDs; reject
  ambiguous identity before authoritative indexing, without overwriting input.
- **Source identity:** opaque raw src within the dataset. Do not derive reliability
  from its name or turn repeated claims into independent source votes.
- **Entity identity:** dataset snapshot plus raw flight; benchmark-only grouping.
  Empty/malformed keys are explicit intake exceptions, never grouped together.
- **Claim:** observation identity plus one of the four time field names and its
  exact raw string. Empty is still evidence of missing reporting, not a time.
- Preserve complete rows, all seven raw strings, original bytes/hash, source ID,
  observation ID, row position, and contract version. Derived values/issues belong
  separately; preserve even unusual or invalid time strings. Do not drop an entire
  observation because one time field is missing or unparseable.
- Future repeated rows from one source remain evidence with explicit duplication
  metadata. A source with conflicting repeated claims is ambiguous; it must not
  gain multiple votes. No deduplication or voting is implemented here.
- This contract is not production aviation identity matching: flight alone lacks
  the guaranteed service-date/timezone semantics needed outside this benchmark.

## Evaluation policy for Milestone 8

Primary unit: original observation cell `(dataset hash, tuple_id, time field)`.
Exclude metadata from accuracy denominators. A discrepancy is a flight/field work
item; an entity result is one selected value; projecting that value back onto all
relevant observations yields many cell outcomes. Report group and cell counts
separately; never count one reviewed group as one corrected source cell.

Let U be eligible aligned time cells, D the original dirty strings, R the reference,
E = {c in U: D[c] != R[c]}, F the frozen explicitly flagged cells. Expand a flagged
group to its original cells by a documented rule fixed before evaluation.

| Detection metric | Definition |
|---|---|
| TP / FP / FN | `|F ∩ E|` / `|F - E|` / `|E - F|` |
| Precision / recall | `TP/(TP+FP)` / `TP/(TP+FN)` |
| F1 | `2TP/(2TP+FP+FN)` |

A proposal is an unapproved baseline/AI suggestion and changes no effective data.
A repair is an explicit human-approved changed value in the frozen projection O.
Unresolved/rejected/abstained cells retain D in that projection and retain their
explicit workflow state. A human approval that makes no change is not a repair.
Let A = {c in U: O[c] != D[c]}.

| Resolution metric | Definition |
|---|---|
| Correct repairs | `|{c in A ∩ E: O[c] == R[c]}|` |
| Harmful repairs | `|{c in A - E: O[c] != R[c]}|` (originally correct, made wrong) |
| Incorrect attempted repairs | `|{c in A ∩ E: O[c] != R[c]}|` (wrong remains wrong) |
| All incorrect repairs | Harmful + incorrect attempted repairs |
| Repair precision | Correct repairs / `|A|` |
| Unchanged valid cells | `|{c in U - A: D[c] == R[c]}|` |
| Remaining incorrect cells | `|{c in U: O[c] != R[c]}|`, including unresolved errors |
| Cell repair coverage | `|A| / |U|`; additionally report `|A ∩ E| / |E|` as error-attempt coverage |
| Decision coverage | Final resolved groups / all queued groups in the frozen workset |
| AI abstention rate | Explicit abstain outcomes / completed valid AI responses; failures counted separately |
| Unresolved cases | Count and rate over frozen queued flight/field groups; separately count projected cells |

All zero denominators are undefined/null, with their counts reported, not silently
100% or 0%. Proposal metrics, when added, must be labeled separately and never
presented as human-approved repairs. Current findings measure no repair performance.

Missing dirty values are eligible cells when their reference is definite. A missing
or internally contradictory reference is unknown: exclude affected cells/groups
from correctness denominators and report exclusions. Duplicate/unmatched IDs or
identity mismatches make a full-run evaluation invalid; do not silently score a
partial join. Structural/encoding errors fail inspection without dumping row values.

Exact-string equality is the primary reproducible policy. A future separately
versioned normalized-equivalence report must define supported transformations,
missing markers, invalid/ambiguous handling, and serialization before evaluation.
Do not assume annotated dates, offsets, or status text can be discarded. No time
normalization implementation or reference-driven policy selection is included here.

Conceptual baselines for later stages: a unique normalized plurality/majority of
independent sources, and a conservative agreement threshold with minimum source
support. Count each source at most once per group; ties, conflicting same-source
claims, insufficient support, or unsupported formats can abstain. Choose and freeze
policies from dirty evidence and synthetic cases, never reference answers. Consensus
does not establish truth. No candidate generation or threshold tuning ran in M2.

Before any future label read, freeze candidates, proposals, decisions, workset,
configuration/prompt/normalization versions, and output hashes. Evaluate a fixed
snapshot; subsequent changes require a new declared run. Any future tuning or
learning requires flight-level partitions, never random related-source row splits.

## Focused verification

```bash
python3 -B -m unittest discover -s scripts -p test_flights_benchmark.py -v
git diff --check
```

All fixtures are synthetic temporary files outside application storage. Tests use
the standard library, do not load backend/tests/conftest.py, import the application,
start services, or touch application databases. Tests cover metadata reproducibility,
quoted/multiline/empty values, source independence, duplicate/missing IDs, shuffled
ID joins, ambiguous/unmatched reference keys, identity mismatches, reference
contradictions, absent reference, read allowlisting, storage/symlink boundaries,
CSV/encoding errors, BOM, Git protection, and runtime import separation.
