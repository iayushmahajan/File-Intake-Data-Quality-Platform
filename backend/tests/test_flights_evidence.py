"""Synthetic evidence semantics; no reference labels, persistence or AI required."""

from dataclasses import asdict, replace
from itertools import permutations
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.reconciliation import evidence as policy
from app.reconciliation.evidence import compare_times, investigate_field, investigation_id
from app.reconciliation.grouping import ObservationIssue, RawObservation, group_flights
from app.reconciliation.normalization import normalize_time


def row(key, src, value, *, position=2, job_id=1, flight="ZZ-1-AAA-BBB", issues=()):
    return RawObservation(job_id, key, position, src, flight, value,
                          "14:25", "14:25", "14:25", issues)


def investigate(rows, field="sched_dep_time"):
    return investigate_field(group_flights(rows).groups[0], field)


def test_format_equivalence_is_one_traceable_candidate_and_not_a_queue_error():
    rows = [row("a", "source-a", "9:22 a.m."), row("b", "source-b", "09:22 AM", position=3)]
    before = [asdict(r) for r in rows]
    result = investigate(rows)
    assert not result.flags.confirmed_conflict and result.flags.formatting_variation
    assert not result.requires_attention
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.canonical_clock == "09:22" and candidate.precision == "minute"
    assert candidate.supporting_observation_ids == ("a", "b")
    assert candidate.supporting_source_ids == ("source-a", "source-b")
    assert set(candidate.raw_values) == {"9:22 a.m.", "09:22 AM"}
    assert not candidate.contradicting_observation_ids
    assert result.baseline.status == "proposal" and result.baseline.candidate_id == candidate.candidate_id
    assert result.baseline.authoritative is False
    assert [asdict(r) for r in rows] == before


def test_conflict_candidates_and_contradictions_are_field_specific():
    rows = [row("a", "source-a", "9:22 AM"), row("b", "source-b", "9:32 AM", position=3)]
    group = group_flights(rows).groups[0]
    result = investigate_field(group, "sched_dep_time")
    assert result.flags.confirmed_conflict and result.requires_attention
    left, right = result.candidates
    assert left.contradicting_candidate_ids == (right.candidate_id,)
    assert left.contradicting_observation_ids == ("b",)
    assert right.contradicting_observation_ids == ("a",)
    assert result.baseline.abstention_reasons == ("tied_source_support",)
    arrival = investigate_field(group, "sched_arr_time")
    assert not arrival.flags.confirmed_conflict and len(arrival.candidates) == 1
    assert arrival.discrepancy_id != result.discrepancy_id


@pytest.mark.parametrize("uncertain", ["9:22", "9:22 AM (Estimated)"])
def test_nonparsed_claims_are_not_contradicting_clock_candidates(uncertain):
    result = investigate([row("a", "source-a", "9:22 AM"),
                          row("b", "source-b", uncertain, position=3)])
    assert not result.flags.confirmed_conflict and result.requires_attention
    assert len(result.candidates) == 1 and result.candidates[0].context_observation_ids == ("b",)
    assert result.candidates[0].contradicting_observation_ids == ()
    assert result.baseline.status == "abstain" and result.baseline.candidate_id is None
    assert result.claims[1].normalization.raw == uncertain


def test_conflict_missing_placeholder_and_unsupported_coexist_without_lost_claims():
    values = ["9:22 AM", "9:32 AM", "", "Not Available", "9:22 PM&nbsp(Estimated)"]
    result = investigate([row(str(i), f"source-{i}", value, position=i + 2)
                          for i, value in enumerate(values)])
    flags = result.flags
    assert flags.confirmed_conflict and flags.has_missing and flags.has_placeholders and flags.has_unsupported
    assert result.counts.missing == result.counts.placeholder == result.counts.unsupported == 1
    assert len(result.claims) == 5 and len(result.candidates) == 2
    assert [claim.normalization.raw for claim in result.claims] == values
    assert result.claims[-1].normalization.reason
    assert "unsupported_claims" in result.baseline.abstention_reasons
    assert result.candidates[0].context_observation_ids == ("2", "3", "4")


def test_precision_mismatch_is_incomparable_even_for_different_clock_text():
    result = investigate([row("a", "source-a", "9:22 AM"),
                          row("b", "source-b", "9:32:00 AM", position=3)])
    assert not result.flags.confirmed_conflict
    assert result.flags.incomparable_supported_values
    assert all(c.incomparable_candidate_ids and not c.contradicting_candidate_ids for c in result.candidates)
    assert "incomparable_supported_values" in result.baseline.abstention_reasons
    assert compare_times(normalize_time("9:22"), normalize_time("9:32 AM")) == "incomparable"


def test_repeated_source_claims_do_not_outvote_distinct_sources():
    rows = [row(str(i), "repeated", "9:22 AM", position=i + 2) for i in range(5)]
    rows += [row("b", "source-b", "9:32 AM", position=7),
             row("c", "source-c", "9:32 AM", position=8)]
    result = investigate(rows)
    first, second = result.candidates
    assert first.observation_support_count == 5 and first.distinct_source_support_count == 1
    assert second.observation_support_count == 2 and second.distinct_source_support_count == 2
    assert result.baseline.status == "proposal" and result.baseline.candidate_id == second.candidate_id
    assert result.usable_source_count == 3 and result.observation_count == 7


def test_internal_source_conflict_is_visible_and_vetoes_even_a_unique_leader():
    rows = [row("a", "same-source", "9:22 AM"), row("b", "same-source", "9:32 AM", position=3),
            row("c", "source-c", "9:22 AM", position=4), row("d", "source-d", "9:22 AM", position=5)]
    result = investigate(rows)
    assert result.internally_inconsistent_source_ids == ("same-source",)
    assert result.flags.internal_source_conflict
    assert result.baseline.status == "abstain"
    assert "internal_source_conflict" in result.baseline.abstention_reasons
    assert sum(c.observation_support_count for c in result.candidates) == 4


def test_no_supported_value_is_an_explicit_abstention_not_an_invented_candidate():
    result = investigate([row("a", "source-a", "9:22"), row("b", "source-b", "Contact Airline", position=3),
                          row("c", "source-c", "unknown text", position=4)])
    assert result.candidates == () and result.candidate_state == "no_supported_candidate"
    assert "no_supported_candidate" in result.baseline.abstention_reasons
    assert result.baseline.candidate_id is None


def test_unavailable_claims_do_not_veto_supported_proposal_but_stay_in_queue():
    result = investigate([row("a", "source-a", "9:22 AM"), row("b", "source-b", "9:22 AM", position=3),
                          row("c", "source-c", "", position=4), row("d", "source-d", "Not Available", position=5)])
    assert result.baseline.status == "proposal" and result.requires_attention
    assert result.counts.missing == result.counts.placeholder == 1
    assert not result.flags.confirmed_conflict
    assert result.candidates[0].distinct_source_support_count == 2


def test_single_source_and_unusable_identities_abstain_without_dropping_values():
    single = investigate([row("a", "source-a", "9:22 AM")])
    assert single.baseline.abstention_reasons == ("insufficient_source_support",)
    issue = ObservationIssue("source_shape", "src", 3, "Unusable source identity")
    result = investigate([row("a", "source-a", "9:22 AM"),
                          row("b", " source-b ", "9:22 AM", position=3, issues=(issue,))])
    assert result.flags.unusable_source_identity and result.usable_source_count == 1
    assert result.candidates[0].observation_support_count == 2
    assert result.candidates[0].supporting_source_ids == ("source-a",)
    assert result.claims[1].identity_issues == (issue,)
    assert "unusable_source_identity" in result.baseline.abstention_reasons


def test_ids_digests_and_order_do_not_depend_on_iteration_order_and_scope_cannot_merge(tmp_path):
    rows = [row("a", "source-a", "9:22 AM"), row("b", "source-b", "9:32 AM", position=3),
            row("c", "source-c", "9:22 AM", position=4)]
    expected = investigate(rows)
    for ordering in permutations(rows):
        assert investigate(ordering) == expected
    group = group_flights(rows).groups[0]
    assert investigate_field(replace(group, observations=tuple(reversed(group.observations))), "sched_dep_time") == expected
    changed = investigate([replace(rows[0], sched_dep_time="09:22 a.m."), *rows[1:]])
    assert changed.discrepancy_id == expected.discrepancy_id
    assert changed.candidates[0].candidate_id == expected.candidates[0].candidate_id
    assert changed.evidence_digest != expected.evidence_digest
    other = investigate([replace(r, job_id=2) for r in rows])
    assert other.discrepancy_id != expected.discrepancy_id
    assert other.candidates[0].candidate_id != expected.candidates[0].candidate_id
    # A separate hash seed/process must produce the same scope ID, with pure imports only.
    code = """
import importlib.abc, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('app.core', 'app.intake', 'app.models', 'inspect_flights')):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Guard())
from app.reconciliation.evidence import investigation_id
print(investigation_id(1, 'ZZ-1-AAA-BBB', 'sched_dep_time'))
"""
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path,
                            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                                 "PYTHONHASHSEED": "123"}, check=True, capture_output=True, text=True)
    assert result.stdout.strip() == expected.discrepancy_id
    assert investigation_id(1, "ZZ-2-AAA-BBB", "sched_dep_time") != expected.discrepancy_id


def test_complete_evidence_limits_fail_instead_of_truncating(monkeypatch):
    rows = [row("a", "source-a", "9:22 AM"), row("b", "source-b", "9:32 AM", position=3)]
    monkeypatch.setattr(policy, "MAX_FIELD_CLAIMS", 1)
    with pytest.raises(policy.EvidenceLimitError, match="claim limit"):
        investigate(rows)
    monkeypatch.setattr(policy, "MAX_FIELD_CLAIMS", 250)
    monkeypatch.setattr(policy, "MAX_FIELD_CANDIDATES", 1)
    with pytest.raises(policy.EvidenceLimitError, match="candidate limit"):
        investigate(rows)
