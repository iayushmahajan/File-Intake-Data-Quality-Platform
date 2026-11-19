"""Synthetic clock semantics; no benchmark answers or provider calls."""

from dataclasses import replace
from pathlib import Path
import os
import subprocess
import sys

import pytest

from app.reconciliation.normalization import (
    NORMALIZATION_POLICY, equivalent_times, normalize_time,
)


def test_explicit_formats_establish_equivalence_without_changing_raw_values():
    variants = ["9:22 a.m.", "09:22 AM", " 9:22\tA. M. "]
    results = [normalize_time(raw) for raw in variants]
    assert [result.raw for result in results] == variants
    assert all(result.status == "parsed" and result.canonical_clock == "09:22" for result in results)
    assert all(result.precision == "minute" and result.policy_version == NORMALIZATION_POLICY
               for result in results)
    assert all(equivalent_times(results[0], result) for result in results)
    assert not equivalent_times(results[0], normalize_time("9:32 a.m."))


@pytest.mark.parametrize("raw,canonical", [
    ("12:00 a.m.", "00:00"), ("12:00 p.m.", "12:00"),
    ("noon", "12:00"), ("12:00noon", "12:00"),
    ("9:22 pm", "21:22"), ("14:25", "14:25"), ("00:15", "00:15"),
])
def test_unambiguous_clock_boundaries(raw, canonical):
    result = normalize_time(raw)
    assert result.status == "parsed" and result.canonical_clock == canonical
    assert equivalent_times(normalize_time("noon"), normalize_time("12:00 p.m."))
    assert not equivalent_times(normalize_time("12:00 a.m."), normalize_time("noon"))


def test_bare_hours_do_not_establish_a_period():
    for raw in ["9:22", "09:22", "12:00", "1:22:33"]:
        result = normalize_time(raw)
        assert result.status == "ambiguous" and result.canonical_clock is None
        assert result.qualifiers == ("period_unspecified",) and result.reason
        assert not equivalent_times(result, normalize_time(raw + " AM"))
        assert not equivalent_times(result, result)


def test_empty_whitespace_and_explicit_unavailability_stay_distinct():
    empty, whitespace = normalize_time(""), normalize_time(" \t\r\n")
    assert empty.status == whitespace.status == "missing"
    assert empty.raw == "" and whitespace.raw == " \t\r\n"
    assert empty.reason != whitespace.reason
    for raw in ["Not Available", " Contact Airline "]:
        result = normalize_time(raw)
        assert result.raw == raw and result.status == "placeholder"
        assert result.canonical_clock is None and result.qualifiers
        assert not equivalent_times(empty, result)
        assert not equivalent_times(result, result)
    assert normalize_time("Dec 2 Not Available").status == "unsupported"
    assert normalize_time("00:00").status == "parsed"
    assert empty.canonical_clock is None


@pytest.mark.parametrize("raw", ["13:10 PM", "00:15 AM", "24:00", "12:60 AM", "14:25:60"])
def test_invalid_components_have_no_canonical_clock(raw):
    result = normalize_time(raw)
    assert result.status == "unsupported" and result.canonical_clock is None
    assert result.reason == "Clock components are outside supported ranges."


@pytest.mark.parametrize("raw", [
    "12/02/2011 6:55 a.m.", "Thu  9:22", "9:22 a.m. (-1:00)",
    "9:22 p.m. (Estimated runway)", "9:22 p.m.    Delayed",
    "9:22 p.m.&nbsp(Estimated)", "9:22 p.m.*", "9:22aDec 2",
    "9:22 A.M. UTC", "9:22:00.123 AM",
])
def test_context_and_unsupported_precision_are_not_discarded(raw):
    result = normalize_time(raw)
    assert result.status == "unsupported" and result.raw == raw
    assert result.canonical_clock is None
    assert result.qualifiers == ("uninterpreted_context",) and result.reason
    assert not equivalent_times(result, normalize_time("9:22 p.m."))


def test_seconds_precision_is_preserved_and_not_merged_with_minutes():
    result = normalize_time("9:22:07 p.m.")
    assert result.canonical_clock == "21:22:07" and result.precision == "second"
    assert equivalent_times(result, normalize_time("21:22:07"))
    assert not equivalent_times(normalize_time("21:22"), normalize_time("21:22:00"))
    assert not equivalent_times(result, normalize_time("21:22:08"))


def test_unicode_html_and_policy_versions_are_not_guessed():
    for raw in ["未定", "９:２２ AM", '<script>alert("x")</script>', "9h22", "9:2 AM"]:
        result = normalize_time(raw)
        assert result.status == "unsupported" and result.raw == raw and result.reason
        assert result == normalize_time(raw)
    parsed = normalize_time("14:25")
    assert parsed.policy_version == "flight_time_normalization_v1"
    assert not equivalent_times(parsed, replace(parsed, policy_version="future_policy"))


def test_pure_modules_import_without_application_or_reference_dependencies(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    code = """
import importlib.abc, sys
class DenyRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'fastapi', 'sqlmodel', 'celery', 'openai'} or fullname.startswith(
            ('app.core', 'app.intake', 'app.models', 'inspect_flights', 'scripts')
        ):
            raise AssertionError('Forbidden runtime import: ' + fullname)
sys.meta_path.insert(0, DenyRuntime())
from app.reconciliation.normalization import normalize_time
from app.reconciliation.grouping import group_flights
assert normalize_time('9:22 AM').canonical_clock == '09:22'
assert group_flights([]).groups == ()
"""
    subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path,
                   env={**os.environ, "PYTHONPATH": str(backend)}, check=True,
                   capture_output=True, text=True)
