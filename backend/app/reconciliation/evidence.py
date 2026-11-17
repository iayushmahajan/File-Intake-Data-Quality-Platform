"""Pure observed-data discrepancies, traceable candidates and a non-authoritative baseline."""

from collections import Counter
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Literal

from app.reconciliation.grouping import FlightGroup, ObservationIssue, TIME_FIELDS, TimeField
from app.reconciliation.normalization import (
    NORMALIZATION_POLICY, NormalizedTime, Precision, equivalent_times,
)

DETECTION_POLICY = "flight_discrepancy_v1"
BASELINE_POLICY = "flight_source_support_baseline_v1"
# Bound complete evidence and its pairwise candidate-reference graph, never truncate it.
MAX_FIELD_CLAIMS = 250
MAX_FIELD_CANDIDATES = 64


class EvidenceLimitError(ValueError):
    pass


@dataclass(frozen=True)
class FieldClaim:
    tuple_id: str
    row_number: int
    src: str
    source_usable: bool
    normalization: NormalizedTime
    identity_issues: tuple[ObservationIssue, ...]


@dataclass(frozen=True)
class StatusCounts:
    parsed: int
    missing: int
    placeholder: int
    ambiguous: int
    unsupported: int


@dataclass(frozen=True)
class EvidenceFlags:
    confirmed_conflict: bool
    has_missing: bool
    has_placeholders: bool
    has_ambiguous: bool
    has_unsupported: bool
    formatting_variation: bool
    incomparable_supported_values: bool
    unusable_source_identity: bool
    internal_source_conflict: bool
    insufficient_support: bool


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    canonical_clock: str
    precision: Precision
    qualifiers: tuple[str, ...]
    raw_values: tuple[str, ...]
    supporting_observation_ids: tuple[str, ...]
    supporting_source_ids: tuple[str, ...]
    observation_support_count: int
    distinct_source_support_count: int
    contradicting_candidate_ids: tuple[str, ...]
    contradicting_observation_ids: tuple[str, ...]
    incomparable_candidate_ids: tuple[str, ...]
    context_observation_ids: tuple[str, ...]
    detection_policy: str = DETECTION_POLICY
    normalization_policy: str = NORMALIZATION_POLICY


AbstentionReason = Literal[
    "no_supported_candidate", "ambiguous_claims", "unsupported_claims",
    "incomparable_supported_values", "unusable_source_identity",
    "internal_source_conflict", "tied_source_support", "insufficient_source_support",
]


@dataclass(frozen=True)
class Baseline:
    status: Literal["proposal", "abstain"]
    candidate_id: str | None
    abstention_reasons: tuple[AbstentionReason, ...]
    policy_version: str = BASELINE_POLICY
    authoritative: Literal[False] = False


@dataclass(frozen=True)
class FieldEvidence:
    discrepancy_id: str
    job_id: int
    flight: str
    field: TimeField
    observation_count: int
    usable_source_count: int
    counts: StatusCounts
    flags: EvidenceFlags
    claims: tuple[FieldClaim, ...]
    candidates: tuple[Candidate, ...]
    candidate_state: Literal["supported_candidates", "no_supported_candidate"]
    internally_inconsistent_source_ids: tuple[str, ...]
    baseline: Baseline
    requires_attention: bool
    summary: str
    evidence_digest: str
    detection_policy: str = DETECTION_POLICY
    normalization_policy: str = NORMALIZATION_POLICY


def _digest(value: object) -> str:
    content = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def investigation_id(job_id: int, flight: str, field: TimeField) -> str:
    return "fld_" + _digest([DETECTION_POLICY, NORMALIZATION_POLICY, job_id, flight, field])


def compare_times(left: NormalizedTime, right: NormalizedTime) -> Literal[
    "equivalent", "conflict", "incomparable"
]:
    if equivalent_times(left, right):
        return "equivalent"
    if (left.status == right.status == "parsed"
            and left.policy_version == right.policy_version == NORMALIZATION_POLICY
            and left.precision == right.precision and left.qualifiers == right.qualifiers
            and left.canonical_clock is not None and right.canonical_clock is not None
            and left.canonical_clock != right.canonical_clock):
        return "conflict"
    return "incomparable"


def investigate_field(group: FlightGroup, field: TimeField) -> FieldEvidence:
    """Investigate one field. No equality failure is promoted to a contradiction."""
    if field not in TIME_FIELDS or not group.observations:
        raise ValueError("A supported field and nonempty flight group are required.")
    if len(group.observations) > MAX_FIELD_CLAIMS:
        raise EvidenceLimitError("Flight field exceeds the complete-evidence claim limit.")
    claims = []
    for item in group.observations:
        row = item.raw
        values = {claim.field: claim.value for claim in item.claims}
        if (row.job_id != group.job_id or row.flight != group.flight
                or len(item.claims) != 4 or set(values) != set(TIME_FIELDS)):
            raise ValueError("Grouped observation identity or field projection is inconsistent.")
        value = values[field]
        if value.policy_version != NORMALIZATION_POLICY or value.raw != getattr(row, field):
            raise ValueError("Normalization policy or raw claim projection is inconsistent.")
        if value.status == "parsed" and (value.canonical_clock is None or value.precision is None):
            raise ValueError("Parsed claims require an explicit clock and precision.")
        claims.append(FieldClaim(
            row.tuple_id, row.row_number, row.src,
            bool(row.src.strip()) and not any(issue.field == "src" for issue in row.issues),
            value, row.issues,
        ))
    claims.sort(key=lambda claim: (claim.row_number, claim.tuple_id))
    if len({claim.tuple_id for claim in claims}) != len(claims):
        raise ValueError("Field evidence contains repeated observation identities.")
    counts = Counter(claim.normalization.status for claim in claims)
    status_counts = StatusCounts(**{status: counts[status] for status in (
        "parsed", "missing", "placeholder", "ambiguous", "unsupported",
    )})
    discrepancy_id = investigation_id(group.job_id, group.flight, field)
    buckets: list[list[FieldClaim]] = []
    for claim in claims:
        if claim.normalization.status != "parsed":
            continue
        for bucket in buckets:
            if equivalent_times(claim.normalization, bucket[0].normalization):
                bucket.append(claim)
                break
        else:
            buckets.append([claim])
            if len(buckets) > MAX_FIELD_CANDIDATES:
                raise EvidenceLimitError("Flight field exceeds the complete-evidence candidate limit.")
    candidates = []
    context_ids = tuple(sorted(claim.tuple_id for claim in claims
                               if claim.normalization.status != "parsed"))
    for bucket in buckets:
        value = bucket[0].normalization
        sources = tuple(sorted({claim.src for claim in bucket if claim.source_usable}))
        candidates.append(Candidate(
            candidate_id="cand_" + _digest([
                discrepancy_id, value.canonical_clock, value.precision, value.qualifiers,
            ]),
            canonical_clock=value.canonical_clock, precision=value.precision,
            qualifiers=value.qualifiers, raw_values=tuple(sorted({c.normalization.raw for c in bucket})),
            supporting_observation_ids=tuple(sorted(c.tuple_id for c in bucket)),
            supporting_source_ids=sources, observation_support_count=len(bucket),
            distinct_source_support_count=len(sources), contradicting_candidate_ids=(),
            contradicting_observation_ids=(), incomparable_candidate_ids=(),
            context_observation_ids=context_ids,
        ))
    candidates.sort(key=lambda c: (c.canonical_clock, c.precision, c.qualifiers))
    claims_by_id = {claim.tuple_id: claim for claim in claims}
    conflicting = {c.candidate_id: [] for c in candidates}
    incomparable = {c.candidate_id: [] for c in candidates}
    inconsistent_sources = set()
    for index, left in enumerate(candidates):
        for right in candidates[index + 1:]:
            relation = compare_times(
                claims_by_id[left.supporting_observation_ids[0]].normalization,
                claims_by_id[right.supporting_observation_ids[0]].normalization,
            )
            if relation == "conflict":
                conflicting[left.candidate_id].append(right)
                conflicting[right.candidate_id].append(left)
                inconsistent_sources.update(set(left.supporting_source_ids) & set(right.supporting_source_ids))
            elif relation == "incomparable":
                incomparable[left.candidate_id].append(right.candidate_id)
                incomparable[right.candidate_id].append(left.candidate_id)
    candidates = tuple(replace(
        candidate,
        contradicting_candidate_ids=tuple(sorted(c.candidate_id for c in conflicting[candidate.candidate_id])),
        contradicting_observation_ids=tuple(sorted(
            key for c in conflicting[candidate.candidate_id] for key in c.supporting_observation_ids
        )),
        incomparable_candidate_ids=tuple(sorted(incomparable[candidate.candidate_id])),
    ) for candidate in candidates)
    leaders = []
    if candidates:
        highest = max(c.distinct_source_support_count for c in candidates)
        leaders = [c for c in candidates if c.distinct_source_support_count == highest]
    insufficient = bool(len(leaders) == 1 and leaders[0].distinct_source_support_count < 2)
    flags = EvidenceFlags(
        confirmed_conflict=any(conflicting.values()), has_missing=bool(counts["missing"]),
        has_placeholders=bool(counts["placeholder"]), has_ambiguous=bool(counts["ambiguous"]),
        has_unsupported=bool(counts["unsupported"]),
        formatting_variation=any(len(c.raw_values) > 1 for c in candidates),
        incomparable_supported_values=any(incomparable.values()),
        unusable_source_identity=any(not c.source_usable for c in claims),
        internal_source_conflict=bool(inconsistent_sources), insufficient_support=insufficient,
    )
    reasons: list[AbstentionReason] = []
    for applies, reason in (
        (not candidates, "no_supported_candidate"), (flags.has_ambiguous, "ambiguous_claims"),
        (flags.has_unsupported, "unsupported_claims"),
        (flags.incomparable_supported_values, "incomparable_supported_values"),
        (flags.unusable_source_identity, "unusable_source_identity"),
        (flags.internal_source_conflict, "internal_source_conflict"),
        (len(leaders) > 1, "tied_source_support"), (insufficient, "insufficient_source_support"),
    ):
        if applies:
            reasons.append(reason)
    baseline = Baseline("abstain", None, tuple(reasons)) if reasons else Baseline(
        "proposal", leaders[0].candidate_id, (),
    )
    summary = (
        f"{len(claims)} observations; {len({c.src for c in claims if c.source_usable})} usable source IDs; "
        f"{len(candidates)} supported clock candidates; {counts['missing']} missing; "
        f"{counts['placeholder']} unavailable; {counts['ambiguous']} ambiguous; "
        f"{counts['unsupported']} unsupported. "
        + ("Confirmed comparable clock disagreement." if flags.confirmed_conflict
           else "No confirmed comparable clock disagreement.")
    )
    evidence = FieldEvidence(
        discrepancy_id, group.job_id, group.flight, field, len(claims),
        len({c.src for c in claims if c.source_usable}), status_counts, flags, tuple(claims),
        candidates, "supported_candidates" if candidates else "no_supported_candidate",
        tuple(sorted(inconsistent_sources)), baseline,
        any(getattr(flags, name) for name in asdict(flags) if name != "formatting_variation"),
        summary, "",
    )
    payload = asdict(evidence)
    del payload["evidence_digest"]
    return replace(evidence, evidence_digest="sha256:" + _digest(payload))
