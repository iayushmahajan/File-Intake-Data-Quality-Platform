"""Explicit OFFLINE evaluation of frozen Flights exports. No DB, HTTP, or provider access."""

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

from inspect_flights import HEADER, REPOSITORY, TIME_FIELDS, decode_flights

# Only the pure feature modules are imported. Never import main, config, review,
# exports, investigations, intake routes, or models in this process.
sys.path.insert(0, str(REPOSITORY / "backend"))
from app.reconciliation.evidence import DETECTION_POLICY, compare_times, investigate_field
from app.reconciliation.grouping import ObservationIssue, RawObservation, group_flights
from app.reconciliation.normalization import NORMALIZATION_POLICY, NormalizedTime, normalize_time

EVALUATION_POLICY = "flight_offline_evaluation_v1"
EVALUATOR_VERSION = "1.0.0"
EXPORT_POLICY = "flight_reviewed_export_v1"
REVIEW_POLICY = "flight_human_review_v1"
LIMIT = 32 * 1024 * 1024
FILES = {"reviewed": "reviewed.csv", "exceptions": "exceptions.csv", "provenance": "provenance.json"}
COLUMNS = ["job_id", "export_id", "flight", *[x for f in TIME_FIELDS for x in (f, f+"_status", f+"_decision_id", f+"_revision")]]
EXCEPTIONS = ["job_id", "export_id", "flight", "field", "discrepancy_id", "review_status", "reason", "decision_id", "revision", "tuple_id", "src", "row_number"]


class IntegrityError(ValueError):
    def __init__(self, code, artifact):
        self.code, self.artifact = code, artifact
        super().__init__(f"{code}: {artifact}")


def require(condition, code, artifact):
    if not condition:
        raise IntegrityError(code, artifact)


def sha(content):
    return hashlib.sha256(content).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def content_digest(value):
    return "sha256:" + sha(canonical(value).encode())


def read_bytes(path, limit=LIMIT):
    path = Path(path).absolute()
    require(path.resolve(strict=True) == path and stat.S_ISREG(path.stat().st_mode), "unsafe_file", path.name)
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    require(len(content) <= limit, "file_budget", path.name)
    return content


def json_value(content, artifact):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_json_key", artifact)
            result[key] = value
        return result
    try:
        return json.loads(content.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(IntegrityError("invalid_json_number", artifact)))
    except (UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, IntegrityError): raise
        raise IntegrityError("invalid_json", artifact) from error


def external(path):
    path = Path(path).absolute()
    require(path.resolve(strict=True) == path and not path.is_relative_to(REPOSITORY), "external_path_required", path.name)
    configured_data = os.environ.get("DATA_DIR")
    if configured_data:
        require(not path.is_relative_to(Path(configured_data).resolve()), "runtime_storage_forbidden", path.name)
    return path


def load_dataset(path, expected_hash):
    content = read_bytes(external(path), 10 * 1024 * 1024)
    require(sha(content) == expected_hash, "dataset_hash", Path(path).name)
    try:
        rows, metadata = decode_flights(content)
    except (UnicodeError, ValueError, csv.Error) as error:
        raise IntegrityError("dataset_structure", Path(path).name) from error
    require(0 < len(rows) <= 5000, "dataset_bound", Path(path).name)
    indexed = {}
    for position, row in enumerate(rows, 2):
        key = row["tuple_id"]
        require(key.strip() and key not in indexed and len(key.encode()) <= 1024 and
                all("\x00" not in v for v in row.values()), "observation_identity", Path(path).name)
        indexed[key] = (position, row)
    return indexed, metadata


def observed_groups(dirty, job_id):
    """Reconstruct the versioned intake identity issues; clock grammar is reused unchanged."""
    observations = []
    for position, row in sorted(dirty.values()):
        issues = []
        for field in ("src", "flight"):
            value = row[field]
            if not value.strip():
                issues.append(ObservationIssue("blank_identity", field, position, f"{field} is blank; retain as an identity exception."))
            elif field == "flight" and not re.fullmatch(r"[A-Z0-9]{2,3}-[0-9]+-[A-Z]{3}-[A-Z]{3}", value):
                issues.append(ObservationIssue("flight_shape", field, position, "flight does not match the bounded benchmark key shape."))
            elif field == "src" and (value != value.strip() or any(ord(c) < 32 for c in value)):
                issues.append(ObservationIssue("source_shape", field, position, "src contains surrounding whitespace or control characters."))
        observations.append(RawObservation(job_id=job_id, row_number=position, issues=tuple(issues), **row))
    return group_flights(observations)


def csv_rows(content, columns, artifact):
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8"), newline=""), strict=True)
        require(next(reader, None) == columns, "csv_header", artifact)
        result = []
        for row in reader:
            require(len(row) == len(columns), "csv_width", artifact)
            # Every original leading apostrophe is escaped too, making this reversible.
            result.append(dict(zip(columns, [v[1:] if v.startswith("'") else v for v in row])))
        return result
    except (UnicodeError, csv.Error) as error:
        raise IntegrityError("csv_structure", artifact) from error


def uuid(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{32}", value))


def candidate_resolution(candidate):
    return dict(origin="observed_candidate", canonical_clock=candidate.canonical_clock,
                precision=candidate.precision, qualifiers=list(candidate.qualifiers),
                supporting_observation_ids=list(candidate.supporting_observation_ids),
                supporting_source_ids=list(candidate.supporting_source_ids))


def validate_decision(entry, evidence, decision_ids):
    status, event, resolution = entry["status"], entry["decision"], entry["resolution"]
    scope = evidence.discrepancy_id
    require(status in ("unreviewed", "accepted", "overridden", "rejected", "unresolved", "stale"), "review_status", scope)
    if event is None:
        require(status == "unreviewed" and resolution is None, "missing_decision", scope)
        return
    require(isinstance(entry, dict), "field_schema", scope)
    required = {"id", "request_id", "job_id", "discrepancy_id", "flight", "field", "evidence_digest", "revision", "action",
                "candidate_id", "investigation_id", "manual_value", "resolution", "rationale", "reviewer_label",
                "policy_version", "normalization_policy", "detection_policy", "created_at"}
    require(isinstance(event, dict) and set(event) == required, "decision_schema", scope)
    require(uuid(event["id"]) and event["id"] not in decision_ids and type(event["revision"]) is int and 0 < event["revision"] <= 2147483647,
            "decision_identity", scope)
    decision_ids.add(event["id"])
    require(isinstance(event["request_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]{8,80}", event["request_id"]), "decision_request", scope)
    datetime.fromisoformat(event["created_at"])
    require(event["investigation_id"] is None or uuid(event["investigation_id"]), "investigation_identity", scope)
    require((event["job_id"], event["discrepancy_id"], event["flight"], event["field"]) ==
            (evidence.job_id, scope, evidence.flight, evidence.field), "decision_scope", scope)
    require((event["policy_version"], event["normalization_policy"], event["detection_policy"]) ==
            (REVIEW_POLICY, NORMALIZATION_POLICY, DETECTION_POLICY), "decision_policy", scope)
    require(isinstance(event["evidence_digest"], str) and re.fullmatch(r"sha256:[0-9a-f]{64}", event["evidence_digest"]), "decision_digest", scope)
    require(isinstance(event["reviewer_label"], str) and event["reviewer_label"].strip() and len(event["reviewer_label"]) <= 80 and not any(ord(c)<32 for c in event["reviewer_label"]) and
            isinstance(event["rationale"], str) and len(event["rationale"]) <= 1000 and not any(ord(c)<32 and c not in "\n\t" for c in event["rationale"]), "reviewer_metadata", scope)
    require(event["action"] in ("accept", "override", "reject", "unresolved"), "decision_action", scope)
    if status == "stale":
        require(event["evidence_digest"] != evidence.evidence_digest and resolution is None, "stale_projection", scope)
        return
    require(event["evidence_digest"] == evidence.evidence_digest, "stale_approval", scope)
    require(status == {"accept": "accepted", "override": "overridden", "reject": "rejected", "unresolved": "unresolved"}[event["action"]], "action_status", scope)
    candidates = {c.candidate_id: c for c in evidence.candidates}
    if event["action"] in ("accept", "reject"):
        require(uuid(event["investigation_id"]) and event["candidate_id"] in candidates and event["manual_value"] is None,
                "investigation_provenance", scope)
    if event["action"] in ("override", "reject"):
        require(event["rationale"].strip(), "missing_rationale", scope)
    if status in ("accepted", "overridden"):
        if event["manual_value"] is not None:
            require(status == "overridden" and event["candidate_id"] is None and isinstance(event["manual_value"], str) and len(event["manual_value"]) <= 160, "manual_provenance", scope)
            value = normalize_time(event["manual_value"])
            require(value.status == "parsed", "manual_clock", scope)
            expected = dict(origin="human_assertion", canonical_clock=value.canonical_clock, precision=value.precision,
                            qualifiers=list(value.qualifiers), supporting_observation_ids=[], supporting_source_ids=[])
        else:
            require(event["candidate_id"] in candidates, "unknown_candidate", scope)
            expected = candidate_resolution(candidates[event["candidate_id"]])
        require(resolution == event["resolution"] == expected, "approved_resolution", scope)
    else:
        require(resolution is None and event["resolution"] is None, "unapproved_value", scope)
        if status == "unresolved":
            require(all(event[key] is None for key in ("candidate_id", "manual_value", "investigation_id")), "hidden_selection", scope)


def verify_export(directory, metadata_path, dirty, dirty_hash):
    metadata = json_value(read_bytes(metadata_path), "export metadata")
    require(isinstance(metadata, dict) and uuid(metadata.get("id")) and type(metadata.get("job_id")) is int and metadata["job_id"] > 0,
            "export_identity", "metadata")
    require(set(metadata) == {"id", "request_id", "job_id", "snapshot_digest", "input_sha256", "policy_version", "created_at", "artifacts"}, "metadata_schema", "metadata")
    require(isinstance(metadata["request_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]{8,80}", metadata["request_id"]), "export_request", "metadata")
    require(metadata.get("policy_version") == EXPORT_POLICY and metadata.get("input_sha256") == dirty_hash, "export_input_or_policy", "metadata")
    require(isinstance(metadata.get("artifacts"), dict) and set(metadata["artifacts"]) == set(FILES), "artifact_inventory", "metadata")
    directory = Path(directory).absolute()
    require(directory.resolve(strict=True) == directory and directory.is_dir(), "artifact_directory", "export")
    data = {key: read_bytes(directory / filename) for key, filename in FILES.items()}
    require(sum(map(len, data.values())) <= LIMIT, "artifact_budget", "export")
    info = {key: {"sha256": sha(value), "bytes": len(value)} for key, value in data.items()}
    require(metadata["artifacts"] == info, "artifact_hash", "export")
    manifest = json_value(data["provenance"], "provenance")
    snapshot = manifest["snapshot"]
    require(isinstance(snapshot, dict) and set(snapshot) == {"job_id", "input_sha256", "contract", "contract_version", "export_policy", "review_policy", "normalization_policy", "detection_policy", "fields", "ungroupable_observations", "unmapped_decisions"}, "snapshot_schema", "provenance")
    require(type(snapshot["job_id"]) is int and type(snapshot["contract_version"]) is int, "snapshot_identity_types", "provenance")
    require(manifest["export_id"] == metadata["id"] and manifest["snapshot_digest"] == metadata["snapshot_digest"] == content_digest(snapshot), "snapshot_digest", "provenance")
    require(datetime.fromisoformat(manifest["generated_at"]) == datetime.fromisoformat(metadata["created_at"]), "export_timestamp", "provenance")
    require(manifest["artifacts"] == {k: info[k] for k in ("reviewed", "exceptions")}, "manifest_artifact_hash", "provenance")
    require((snapshot["job_id"], snapshot["input_sha256"], snapshot["contract"], snapshot["contract_version"], snapshot["export_policy"],
             snapshot["review_policy"], snapshot["normalization_policy"], snapshot["detection_policy"]) ==
            (metadata["job_id"], dirty_hash, "raha_flights_v1", 1, EXPORT_POLICY, REVIEW_POLICY, NORMALIZATION_POLICY, DETECTION_POLICY), "snapshot_policy", "provenance")
    require(snapshot["unmapped_decisions"] == [], "unmapped_decisions", "provenance")
    grouped = observed_groups(dirty, metadata["job_id"])
    fields = {e.discrepancy_id: e for group in grouped.groups for name in TIME_FIELDS for e in [investigate_field(group, name)]}
    require(isinstance(snapshot["fields"], list) and len(snapshot["fields"]) == len(fields), "field_coverage", "provenance")
    seen, decisions, expected_reviewed, expected_exceptions = set(), set(), {}, []
    projections = {}
    for entry in snapshot["fields"]:
        require(isinstance(entry, dict) and set(entry) == {"discrepancy_id", "flight", "field", "evidence_digest", "status", "resolution", "decision", "observations"}, "field_schema", "provenance")
        key = entry["discrepancy_id"]
        require(key in fields and key not in seen, "duplicate_or_unknown_field", "provenance")
        seen.add(key)
        evidence = fields[key]
        require((entry["flight"], entry["field"], entry["evidence_digest"]) ==
                (evidence.flight, evidence.field, evidence.evidence_digest), "field_evidence_digest", key)
        expected_observations = [dict(tuple_id=c.tuple_id, src=c.src, row_number=c.row_number, source_usable=c.source_usable) for c in evidence.claims]
        require(isinstance(entry["observations"], list) and all(isinstance(o,dict) and type(o.get("source_usable")) is bool for o in entry["observations"]) and entry["observations"] == expected_observations, "observation_mapping", key)
        validate_decision(entry, evidence, decisions)
        if entry["decision"]:
            require(datetime.fromisoformat(entry["decision"]["created_at"]) <= datetime.fromisoformat(manifest["generated_at"]), "future_decision", key)
        event, value, status = entry["decision"], entry["resolution"], entry["status"]
        row = expected_reviewed.setdefault(evidence.flight, {"job_id": str(metadata["job_id"]), "export_id": metadata["id"], "flight": evidence.flight})
        decision_id, revision = (event["id"], str(event["revision"])) if event else ("", "0")
        row.update({evidence.field: value["canonical_clock"] if value else "", evidence.field+"_status": status,
                    evidence.field+"_decision_id": decision_id, evidence.field+"_revision": revision})
        if value is None:
            expected_exceptions.append(dict(job_id=str(metadata["job_id"]), export_id=metadata["id"], flight=evidence.flight,
                field=evidence.field, discrepancy_id=key, review_status=status, reason="stale_review" if status == "stale" else "no_human_approved_value",
                decision_id=decision_id, revision=revision, tuple_id="", src="", row_number=""))
        for claim in evidence.claims:
            cell = (claim.tuple_id, evidence.field)
            require(cell not in projections, "duplicate_cell_projection", key)
            projections[cell] = (value, status)
    expected_ungroupable = []
    for item in grouped.ungroupable:
        raw = item.observation.raw
        expected_ungroupable.append(dict(tuple_id=raw.tuple_id, src=raw.src, flight=raw.flight, row_number=raw.row_number,
            reason=item.reason, fields=list(TIME_FIELDS), issues=[asdict(i) for i in raw.issues]))
        expected_exceptions.append(dict(job_id=str(metadata["job_id"]), export_id=metadata["id"], flight=raw.flight, field="", discrepancy_id="",
            review_status="ungroupable", reason=item.reason, decision_id="", revision="0", tuple_id=raw.tuple_id, src=raw.src, row_number=str(raw.row_number)))
        for name in TIME_FIELDS:
            projections[(raw.tuple_id, name)] = (None, "ungroupable")
    require(snapshot["ungroupable_observations"] == expected_ungroupable, "ungroupable_mapping", "provenance")
    require(len(projections) == len(dirty) * 4, "cell_coverage", "provenance")
    actual = csv_rows(data["reviewed"], COLUMNS, "reviewed")
    require(sorted(actual, key=canonical) == sorted(expected_reviewed.values(), key=canonical), "reviewed_csv_projection", "reviewed")
    actual = csv_rows(data["exceptions"], EXCEPTIONS, "exceptions")
    require(sorted(actual, key=canonical) == sorted(expected_exceptions, key=canonical), "exceptions_csv_projection", "exceptions")
    return metadata, snapshot, fields, projections


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator, "value": numerator / denominator if denominator else None}


def semantic(left, right):
    return {"equivalent": "equal", "conflict": "different", "incomparable": "unknown"}[compare_times(left, right)]


def approved_clock(value):
    return NormalizedTime(value["canonical_clock"], "parsed", value["canonical_clock"], value["precision"], tuple(value["qualifiers"]))


def policy_metrics(dirty, reference, fields, projections, semantic_policy):
    counts = Counter()
    original_results, final_results, exclusions = Counter(), Counter(), Counter()
    original_by_cell = {}
    for key, (_, row) in sorted(dirty.items()):
        for field in TIME_FIELDS:
            value, status = projections[(key, field)]
            original, target = row[field], reference[key][1][field]
            final = value["canonical_clock"] if value else original
            if semantic_policy:
                left, right = normalize_time(original), normalize_time(target)
                after = approved_clock(value) if value else left
                before_result, after_result, changed = semantic(left, right), semantic(after, right), semantic(left, after)
                if before_result == "unknown": exclusions["original_reference_" + ("incompatible_precision_or_qualifiers" if left.status == right.status == "parsed" else left.status + "_" + right.status)] += 1
                if after_result == "unknown": exclusions["final_reference_" + ("incompatible_precision_or_qualifiers" if after.status == right.status == "parsed" else after.status + "_" + right.status)] += 1
                if changed == "unknown": exclusions["original_final_comparison_not_established"] += 1
            else:
                before_result = "equal" if original == target else "different"
                after_result = "equal" if final == target else "different"
                changed = "equal" if original == final else "different"
            original_by_cell[(key, field)] = before_result
            original_results[before_result] += 1
            final_results[after_result] += 1
            counts["cells_total"] += 1
            counts["approved_cells"] += value is not None
            counts["approved_raw_string_changes"] += bool(value and final != original)
            if "unknown" in (before_result, after_result, changed):
                counts["outcome_unscorable_cells"] += 1
                continue
            counts["outcome_scorable_cells"] += 1
            old_wrong, new_wrong, changed = before_result == "different", after_result == "different", changed == "different"
            counts["original_errors"] += old_wrong
            counts["originally_valid"] += not old_wrong
            counts["approved_changes"] += bool(value and changed)
            counts["corrected_errors"] += old_wrong and changed and not new_wrong
            counts["harmful_repairs"] += not old_wrong and changed and new_wrong
            counts["wrong_to_wrong_changes"] += old_wrong and changed and new_wrong
            counts["unchanged_valid_cells"] += not old_wrong and not new_wrong
            counts["remaining_errors"] += new_wrong
            counts["unchanged_original_errors"] += old_wrong and not changed
            counts["approved_no_change_cells"] += bool(value and not changed)
    # Materialize zero counts so absence is never mistaken for an unavailable metric.
    for name in ("cells_total", "approved_cells", "approved_raw_string_changes", "outcome_unscorable_cells", "outcome_scorable_cells",
                 "original_errors", "originally_valid", "approved_changes", "corrected_errors", "harmful_repairs", "wrong_to_wrong_changes",
                 "unchanged_valid_cells", "remaining_errors", "unchanged_original_errors", "approved_no_change_cells"):
        counts[name] += 0
    confusion = Counter(dict(true_positives=0, false_positives=0, false_negatives=0, true_negatives=0, unscorable_groups=0))
    for evidence in fields.values():
        truth = [original_by_cell[(claim.tuple_id, evidence.field)] for claim in evidence.claims]
        if "different" in truth:
            positive = True
        elif "unknown" in truth:
            confusion["unscorable_groups"] += 1
            continue
        else:
            positive = False
        label = ("true_positives" if positive else "false_positives") if evidence.requires_attention else ("false_negatives" if positive else "true_negatives")
        confusion[label] += 1
    tp, fp, fn = (confusion[name] for name in ("true_positives", "false_positives", "false_negatives"))
    return dict(
        unit="original observation time cell; repair outcomes use the jointly scorable cohort",
        counts=dict(sorted(counts.items())),
        original_reference={key: original_results[key] for key in ("equal", "different", "unknown")},
        final_reference={key: final_results[key] for key in ("equal", "different", "unknown")},
        exclusions=dict(sorted(exclusions.items())),
        repair_precision=ratio(counts["corrected_errors"], counts["approved_changes"]),
        correction_recall=ratio(counts["corrected_errors"], counts["original_errors"]),
        harmful_change_rate=ratio(counts["harmful_repairs"], counts["approved_changes"]),
        detection=dict(unit="groupable flight/field, not individual source-cell localization",
                       predicted_positive="Unchanged flight_discrepancy_v1 FieldEvidence.requires_attention",
                       reference_positive="At least one proven original/reference difference; negative only if every cell is equal; otherwise unscorable",
                       groups_total=len(fields), groups_scorable=len(fields)-confusion["unscorable_groups"], **dict(confusion),
                       precision=ratio(tp, tp+fp), recall=ratio(tp, tp+fn), f1=ratio(2*tp, 2*tp+fp+fn)),
    )


def _evaluate(export_dir, metadata_path, dirty_path, reference_path, *, synthetic_manifest=None, evaluated_at=None):
    """All frozen/dirty validation precedes the first reference-file read."""
    source_path = Path(synthetic_manifest) if synthetic_manifest else REPOSITORY / "docs/flights-source-manifest.json"
    source_bytes = read_bytes(source_path)
    source = json_value(source_bytes, "source manifest")
    if synthetic_manifest:
        require(source.get("synthetic") is True and not source.get("upstream_commit"), "synthetic_identity", "source manifest")
    else:
        require(source.get("upstream_commit") == "7be1334b8c7bbdac3f47ef514fb3e1e8c5fc181c", "benchmark_pin", "source manifest")
    require(source.get("dataset_type") == "raha_flights_v1", "benchmark_contract", "source manifest")
    dirty, dirty_metadata = load_dataset(dirty_path, source["files"]["observed"]["sha256"])
    metadata, snapshot, fields, projections = verify_export(export_dir, metadata_path, dirty, dirty_metadata["sha256"])
    # No candidate construction, decision creation or provider operation occurs below.
    reference, reference_metadata = load_dataset(reference_path, source["files"]["evaluation_reference"]["sha256"])
    require(dirty.keys() == reference.keys(), "alignment_keys", "reference")
    for key in dirty:
        require(all(dirty[key][1][name] == reference[key][1][name] for name in ("src", "flight")), "alignment_identity", "reference")
    targets = {}
    for _, row in reference.values():
        if not row["flight"].strip(): continue
        for field in TIME_FIELDS:
            group = (row["flight"], field)
            if group in targets:
                require(targets[group] == row[field], "contradictory_reference", "reference")
            targets[group] = row[field]
    states = Counter(entry["status"] for entry in snapshot["fields"])
    cells = Counter(status for value, status in projections.values())
    approved_fields = states["accepted"] + states["overridden"]
    approved_cells = sum(value is not None for value, status in projections.values())
    report = dict(
        evaluation_policy=EVALUATION_POLICY, evaluator_version=EVALUATOR_VERSION,
        evaluated_at=evaluated_at or datetime.now(timezone.utc).isoformat(),
        benchmark=dict(kind="synthetic" if synthetic_manifest else "pinned_raha_flights", upstream_commit=source.get("upstream_commit"),
                       source_manifest_sha256=sha(source_bytes), dirty=dirty_metadata, reference=reference_metadata),
        export=dict(id=metadata["id"], job_id=metadata["job_id"], snapshot_digest=metadata["snapshot_digest"], artifacts=metadata["artifacts"]),
        alignment=dict(method="tuple_id bijection; raw src/flight match; reference raw group consistency", joined_rows=len(dirty),
                       unique_ids=True, unmatched_dirty_ids=0, unmatched_reference_ids=0, identity_mismatches=0,
                       contradictory_reference_groups=0,
                       row_order_ids_equal=[key for key,_ in sorted(dirty.items(), key=lambda item:item[1][0])] == [key for key,_ in sorted(reference.items(), key=lambda item:item[1][0])],
                       reference_empty_time_cells=sum(row[f] == "" for _,row in reference.values() for f in TIME_FIELDS),
                       time_cells=len(projections), ungroupable_observations=len(snapshot["ungroupable_observations"])),
        exact_string=policy_metrics(dirty, reference, fields, projections, False),
        conservative_semantic=policy_metrics(dirty, reference, fields, projections, True),
        coverage=dict(approved_cells=ratio(approved_cells, len(projections)), unapproved_cells=ratio(len(projections)-approved_cells, len(projections)),
                      approved_fields=ratio(approved_fields, len(fields)),
                      reviewed_current_fields=ratio(sum(states[s] for s in ("accepted", "overridden", "rejected", "unresolved")), len(fields)),
                      field_states={s: states[s] for s in ("unreviewed", "accepted", "overridden", "rejected", "unresolved", "stale")},
                      cell_states=dict(sorted(cells.items())), no_deterministic_candidate_fields=sum(not e.candidates for e in fields.values()),
                      ai_states=dict(available=False, not_requested=None, abstained=None, unavailable_or_failed=None,
                                     reason="Frozen v1 export does not capture complete AI lifecycle; absence of a link is not proof of not-requested.")),
        limitations=["Exact strings count formatting changes as errors, including canonical output versus differently formatted reference text.",
                     "Semantic repair outcomes require original/reference, final/reference and original/final comparisons to be established; exclusions can overlap.",
                     "Unapproved cells retain original values only in offline evaluation; operational exports still leave those approved-value columns empty.",
                     "The attention queue intentionally includes uncertainty and missingness; detection precision measures agreement of that workflow predicate with benchmark group labels.",
                     "Group detection does not locate individual erroneous observations. Ungroupable cells participate in repair/coverage but not group detection.",
                     "Reference labels are a benchmark reference, not independently verified aviation truth; missing reference clocks remain exact-string scorable but semantic-unscorable.",
                     "Hashes check consistency against supplied trusted published metadata; they are not signatures or proof of authenticated human identity or historical AI execution.",
                     "Baseline and AI proposal comparisons are deferred; neither fills unapproved cells. No tuning or live integrations occur.",
                     "Invocation timestamp is variable; other report content is deterministic for identical bytes and frozen identities."],
    )
    return report


def evaluate(export_dir, metadata_path, dirty_path, reference_path, *, synthetic_manifest=None, evaluated_at=None):
    try:
        return _evaluate(export_dir, metadata_path, dirty_path, reference_path,
                         synthetic_manifest=synthetic_manifest, evaluated_at=evaluated_at)
    except IntegrityError:
        raise
    except OSError as error:
        raise IntegrityError("missing_or_unavailable_file", "evaluation input") from error
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as error:
        raise IntegrityError("invalid_contract_structure", "evaluation input") from error


def write_report(path, report, inputs):
    path = Path(path).absolute()
    require(not path.is_relative_to(REPOSITORY) and path.resolve() == path, "evaluation_output_external", "output")
    runtime = os.environ.get("DATA_DIR")
    require(not runtime or not path.is_relative_to(Path(runtime).resolve()), "runtime_storage_forbidden", "output")
    for location in inputs:
        location = Path(location).resolve()
        require(not path.is_relative_to(location if location.is_dir() else location.parent), "evaluation_output_separation", "output")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".evaluation-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write((json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+"\n").encode())
            stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, path)  # Exclusive publication; never overwrite an earlier report.
    finally:
        if temporary: temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("export-dir", "metadata", "dirty", "reference", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--synthetic-manifest", type=Path)
    args = parser.parse_args()
    try:
        report = evaluate(args.export_dir, args.metadata, args.dirty, args.reference, synthetic_manifest=args.synthetic_manifest)
        write_report(args.output, report, [args.export_dir, args.metadata, args.dirty, args.reference])
    except IntegrityError as error:
        parser.exit(2, json.dumps({"error": error.code, "artifact": error.artifact})+"\n")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        parser.exit(2, json.dumps({"error": "invalid_or_unavailable_evaluation_input"})+"\n")
    print(json.dumps({"evaluation_policy": EVALUATION_POLICY, "benchmark_kind": report["benchmark"]["kind"],
                      "observation_cells": report["alignment"]["time_cells"],
                      "corrected_exact": report["exact_string"]["counts"]["corrected_errors"],
                      "harmful_exact": report["exact_string"]["counts"]["harmful_repairs"], "report": str(args.output)}))


if __name__ == "__main__":
    main()
