"""Pure grouping invariants and read-only integration with disposable Flights imports."""

from dataclasses import asdict, replace
from itertools import permutations

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event
from sqlmodel import Session, select

from app.core.config import INPUT_DIR
from app.core.db import engine
from app.intake.flights import FLIGHTS_FIELDS
from app.main import app
from app.models.processing_job import FlightObservation, JobImport, ProcessingJob
from app.reconciliation.grouping import (
    ObservationIssue, RawObservation, TIME_FIELDS, group_flights,
)
from app.reconciliation import observations as projection
from app.reconciliation.observations import load_grouped_flights
from app.services.job_processing import process_job
from test_flights_intake import csv_bytes, observation, submit
from test_uploads import VALID_CSV


def raw(key, position, *, job_id=1, src="source-a", flight="ZZ-1-AAA-BBB", issues=()):
    return RawObservation(job_id, key, position, src, flight, "9:22 a.m.",
                          "9:22", "Not Available", "9:22 p.m. (Estimated)", issues)


def test_snapshot_groups_source_references_ordering_and_raw_claims():
    rows = [raw("a", 2), raw("b", 3, src="source-b"), raw("c", 4),
            raw("d", 5, flight="ZZ-2-AAA-BBB"), raw("a", 2, job_id=2)]
    before = [asdict(row) for row in rows]
    result = group_flights(reversed(rows))
    assert [(g.job_id, g.flight) for g in result.groups] == [
        (1, "ZZ-1-AAA-BBB"), (1, "ZZ-2-AAA-BBB"), (2, "ZZ-1-AAA-BBB"),
    ]
    group = result.groups[0]
    assert group.observation_ids == ("a", "b", "c") and group.observation_count == 3
    assert group.distinct_source_count == 2
    assert [(s.src, s.tuple_ids, s.row_numbers) for s in group.source_references] == [
        ("source-a", ("a", "c"), (2, 4)), ("source-b", ("b",), (3,)),
    ]
    claims = group.observations[0].claims
    assert tuple(claim.field for claim in claims) == TIME_FIELDS == FLIGHTS_FIELDS[3:]
    assert [claim.value.status for claim in claims] == ["parsed", "ambiguous", "placeholder", "unsupported"]
    assert [claim.value.raw for claim in claims] == [getattr(rows[0], field) for field in TIME_FIELDS]
    assert [asdict(row) for row in rows] == before
    assert group_flights(rows) == result
    assert not result.ungroupable


def test_ungroupable_issues_preserve_all_values_and_are_order_independent():
    flagged = ObservationIssue("flight_shape", "flight", 4, "Malformed benchmark identity.")
    # Even a superficially valid spelling remains ungroupable when intake flagged it.
    rows = [raw("good", 2), raw("missing", 3, flight=" \t"),
            raw("bad", 4, flight="malformed", issues=(flagged,)),
            raw("flagged", 5, issues=(replace(flagged, row_number=5),))]
    expected = group_flights(rows)
    assert expected.groups[0].observation_ids == ("good",)
    assert [(item.observation.raw.tuple_id, item.reason) for item in expected.ungroupable] == [
        ("missing", "missing_flight"), ("bad", "flagged_flight"), ("flagged", "flagged_flight"),
    ]
    assert expected.ungroupable[0].observation.raw.flight == " \t"
    assert expected.ungroupable[1].observation.raw.issues == (flagged,)
    for ordering in permutations(rows):
        assert group_flights(ordering) == expected


def test_unusable_source_identity_does_not_drop_an_observation():
    issue = ObservationIssue("source_shape", "src", 4, "Source shape issue.")
    rows = [raw("known", 2), raw("missing-source", 3, src=""),
            raw("bad-source", 4, src=" source-a ", issues=(issue,))]
    group = group_flights(rows).groups[0]
    assert group.observation_count == 3 and group.distinct_source_count == 1
    assert group.observations[1].raw.src == ""
    assert group.observations[2].raw.src == " source-a "


def test_repeated_observation_identity_or_position_is_an_explicit_input_error():
    for rows in [[raw("same", 2), raw("same", 3)], [raw("a", 2), raw("b", 2)]]:
        with pytest.raises(ValueError, match="repeats"):
            group_flights(rows)
    assert group_flights([]).groups == group_flights([]).ungroupable == ()


def test_persisted_projection_pages_complete_groups_without_any_writes():
    rows = [observation("first", value=' 9:22 a.m. '), observation("second", src="source-b"),
            observation("third", value='9:22 p.m. (Estimated)\r\n未定'),
            observation("other", flight="ZZ-2-AAA-BBB"), observation("missing", flight=""),
            observation("malformed", flight="bad identity")]
    content = csv_bytes(rows)
    with TestClient(app) as client:
        first, second = submit(client, content), submit(client, content)
        assert process_job(first) == process_job(second) == "completed"
        with Session(engine) as session:
            stored = session.exec(select(FlightObservation).order_by(
                FlightObservation.job_id, FlightObservation.row_number
            )).all()
            before = [row.model_dump() for row in stored]
            job_before = session.get(ProcessingJob, first).model_dump()
        statements = []

        def record_sql(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record_sql)
        try:
            with Session(engine) as session:
                projected = load_grouped_flights(session, first, batch_size=2)
                other = load_grouped_flights(session, second, batch_size=2)
                assert not session.new and not session.dirty and not session.deleted
        finally:
            event.remove(engine, "before_cursor_execute", record_sql)
        assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements)
        assert len([sql for sql in statements if "FROM flight_observations" in sql]) == 8
        assert projected.groups[0].observation_ids == ("first", "second", "third")
        assert projected.groups[0].observation_count == 3  # Crosses batch boundaries.
        assert projected.groups[0].distinct_source_count == 2
        assert all(group.job_id == first for group in projected.groups)
        assert all(group.job_id == second for group in other.groups)
        assert len(projected.ungroupable) == len(other.ungroupable) == 2
        with Session(engine) as session:
            after = session.exec(select(FlightObservation).order_by(
                FlightObservation.job_id, FlightObservation.row_number
            )).all()
            assert [row.model_dump() for row in after] == before
            assert session.get(ProcessingJob, first).model_dump() == job_before
            filename = session.get(ProcessingJob, first).filename_input_saved
        assert (INPUT_DIR / filename).read_bytes() == content
        for item in projected.groups[0].observations:
            assert tuple(claim.value.raw for claim in item.claims) == tuple(
                getattr(item.raw, field) for field in TIME_FIELDS
            )


def test_projection_rejects_unavailable_wrong_kind_and_invalid_batch_requests():
    with TestClient(app) as client:
        pending = submit(client)
        failed = submit(client, b"bad header\n")
        assert process_job(failed) == "failed"
        legacy = client.post("/api/v1/uploads", files={"file": ("legacy.csv", VALID_CSV)}).json()["job_id"]
        assert process_job(legacy) == "completed"
        with Session(engine) as session:
            with pytest.raises(LookupError, match="not found"):
                load_grouped_flights(session, 999999)
            for job_id in [pending, failed, legacy]:
                with pytest.raises(ValueError, match="completed raha_flights_v1"):
                    load_grouped_flights(session, job_id)
            for size in [0, 101, True]:
                with pytest.raises(ValueError, match="Batch size"):
                    load_grouped_flights(session, pending, batch_size=size)
        assert client.get(f"/api/v1/jobs/{legacy}").json()["status"] == "completed"


def test_projection_fails_closed_on_bounds_version_counts_and_pending_writes(monkeypatch):
    with TestClient(app) as client:
        job_id = submit(client, csv_bytes([observation("one"), observation("two")]))
        assert process_job(job_id) == "completed"
        monkeypatch.setattr(projection, "MAX_GROUPING_OBSERVATIONS", 1)
        with Session(engine) as session, pytest.raises(ValueError, match="grouping bound"):
            load_grouped_flights(session, job_id)
        monkeypatch.setattr(projection, "MAX_GROUPING_OBSERVATIONS", 5000)
        with Session(engine) as session:
            job = session.get(ProcessingJob, job_id)
            job.filename_original = "pending-edit.csv"
            with pytest.raises(ValueError, match="clean session"):
                load_grouped_flights(session, job_id)
            session.rollback()
            metadata = session.get(JobImport, job_id)
            metadata.options = {"contract_version": 999}
            session.add(metadata)
            session.commit()
            with pytest.raises(ValueError, match="contract version"):
                load_grouped_flights(session, job_id)
            metadata.options = {"contract_version": 1}
            session.add(metadata)
            session.commit()
            job = session.get(ProcessingJob, job_id)
            job.total_rows = 3  # Simulate inconsistent disposable storage; do not return partial evidence.
            session.add(job)
            session.commit()
            with pytest.raises(ValueError, match="job count"):
                load_grouped_flights(session, job_id, batch_size=1)
