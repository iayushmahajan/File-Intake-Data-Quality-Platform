"""Read-only evidence APIs against isolated synthetic imports and database state."""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event
from sqlmodel import Session, select

from app.core.config import INPUT_DIR
from app.core.db import engine
from app.main import app
from app.models.processing_job import FlightObservation, JobImport, ProcessingJob
from app.reconciliation import evidence as policy, observations as projection
from app.services.job_processing import process_job
from test_flights_intake import csv_bytes, observation, submit
from test_uploads import VALID_CSV


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def dataset(client):
    rows = [observation("one", value="9:22 AM"),
            observation("two", src="source-b", value="9:32 AM"),
            observation("three", flight="ZZ-2-AAA-BBB", value="9:22 AM"),
            observation("four", src="source-b", flight="ZZ-2-AAA-BBB", value="09:22 a.m."),
            observation("ungroupable", flight="")]
    # Other fields are confidently equivalent for the two usable flight groups.
    for row in rows:
        row[4:] = ["14:25", "15:25", "16:25"]
    content = csv_bytes(rows)
    job_id = submit(client, content)
    assert process_job(job_id) == "completed"
    return job_id, content


def test_list_detail_filters_pagination_and_evidence_are_typed_and_read_only(client):
    job_id, content = dataset(client)
    url = f"/api/v1/flights/jobs/{job_id}/discrepancies"
    with Session(engine) as session:
        stored = session.exec(select(FlightObservation).order_by(FlightObservation.row_number)).all()
        before = [row.model_dump() for row in stored]
        job_before = session.get(ProcessingJob, job_id).model_dump()
        metadata_before = session.get(JobImport, job_id).model_dump()
        filename = job_before["filename_input_saved"]
    statements = []

    def record_sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_sql)
    try:
        response = client.get(url)
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["total"] == 1 and page["ungroupable_observation_count"] == 1
        assert page["raw_observations_url"] == f"/api/v1/flights/jobs/{job_id}/observations"
        summary = page["discrepancies"][0]
        assert summary["flags"]["confirmed_conflict"]
        assert summary["candidate_count"] == summary["usable_source_count"] == 2
        assert summary["baseline"]["status"] == "abstain"
        detail = client.get(url + "/" + summary["discrepancy_id"])
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["job_id"] == job_id and body["field"] == "sched_dep_time"
        assert body["evidence_digest"] == summary["evidence_digest"]
        assert {claim["tuple_id"] for claim in body["claims"]} == {"one", "two"}
        assert {claim["normalization"]["raw"] for claim in body["claims"]} == {"9:22 AM", "9:32 AM"}
        assert all(candidate["supporting_observation_ids"] and candidate["contradicting_observation_ids"]
                   for candidate in body["candidates"])
        assert client.get(url + "/" + summary["discrepancy_id"]).json() == body
        all_fields = client.get(url + "?kind=all&page_size=100").json()
        assert all_fields["total"] == 8
        keys = [(r["flight"], r["field"]) for r in all_fields["discrepancies"]]
        assert keys[:4] == [("ZZ-1-AAA-BBB", field) for field in (
            "sched_dep_time", "act_dep_time", "sched_arr_time", "act_arr_time",
        )]
        assert client.get(url + "?kind=all&page_size=1&page=2").json()["discrepancies"] == all_fields["discrepancies"][1:2]
        assert client.get(url + "?page=999").json()["discrepancies"] == []
        assert client.get(url + "?kind=conflict").json()["total"] == 1
        assert client.get(url + "?kind=missing").json()["total"] == 0
        assert client.get(url + "?kind=uncertain").json()["total"] == 0
        assert client.get(url + "?field=act_arr_time").json()["total"] == 0
        assert client.get(url + "?field=act_arr_time&kind=all").json()["total"] == 2
        assert client.post(url + "/" + summary["discrepancy_id"]).status_code == 405
    finally:
        event.remove(engine, "before_cursor_execute", record_sql)
    assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements)
    with Session(engine) as session:
        after = session.exec(select(FlightObservation).order_by(FlightObservation.row_number)).all()
        assert [row.model_dump() for row in after] == before
        assert session.get(ProcessingJob, job_id).model_dump() == job_before
        assert session.get(JobImport, job_id).model_dump() == metadata_before
    assert (INPUT_DIR / filename).read_bytes() == content
    schemas = app.openapi()["components"]["schemas"]
    assert {"FieldEvidence", "Candidate", "DiscrepancyPage", "DiscrepancySummary"} <= schemas.keys()


def test_unknown_discrepancy_and_job_boundaries_do_not_leak_other_snapshots(client):
    first, content = dataset(client)
    second = submit(client, content)
    assert process_job(second) == "completed"
    url = f"/api/v1/flights/jobs/{first}/discrepancies"
    key = client.get(url).json()["discrepancies"][0]["discrepancy_id"]
    assert client.get(f"/api/v1/flights/jobs/{second}/discrepancies/{key}").status_code == 404
    assert client.get(url + "/unknown").status_code == 404
    assert client.get("/api/v1/flights/jobs/999999/discrepancies").status_code == 404
    assert client.get("/api/v1/flights/jobs/999999/discrepancies/unknown").status_code == 404
    pending = submit(client)
    failed = submit(client, b"bad header\n")
    assert process_job(failed) == "failed"
    legacy = client.post("/api/v1/uploads", files={"file": ("legacy.csv", VALID_CSV)}).json()["job_id"]
    assert process_job(legacy) == "completed"
    for job_id in [pending, failed, legacy]:
        assert client.get(f"/api/v1/flights/jobs/{job_id}/discrepancies").status_code == 409
        assert client.get(f"/api/v1/flights/jobs/{job_id}/discrepancies/unknown").status_code == 409
    for query in ["page=0", "page_size=101", "page_size=0", "kind=bogus", "field=src", "page=text"]:
        assert client.get(url + "?" + query).status_code == 422


def test_uncertain_missing_and_ungroupable_records_are_explicit(client):
    content = csv_bytes([observation("one", value="9:22"),
                         observation("two", src="source-b", value="Not Available"),
                         observation("blank-flight", flight="")])
    job_id = submit(client, content)
    assert process_job(job_id) == "completed"
    url = f"/api/v1/flights/jobs/{job_id}/discrepancies"
    response = client.get(url + "?field=sched_dep_time&kind=uncertain").json()
    assert response["total"] == 1 and response["ungroupable_observation_count"] == 1
    key = response["discrepancies"][0]["discrepancy_id"]
    body = client.get(url + "/" + key).json()
    assert body["candidate_state"] == "no_supported_candidate"
    assert body["flags"]["has_ambiguous"] and body["flags"]["has_placeholders"]
    assert body["baseline"]["candidate_id"] is None and body["baseline"]["authoritative"] is False
    only_bad = submit(client, csv_bytes([observation("bad", flight="")]))
    assert process_job(only_bad) == "completed"
    page = client.get(f"/api/v1/flights/jobs/{only_bad}/discrepancies").json()
    assert page["total"] == 0 and page["ungroupable_observation_count"] == 1


def test_projection_and_evidence_limits_refuse_partial_api_results(client, monkeypatch):
    job_id, _ = dataset(client)
    url = f"/api/v1/flights/jobs/{job_id}/discrepancies"
    key = client.get(url).json()["discrepancies"][0]["discrepancy_id"]
    monkeypatch.setattr(projection, "MAX_GROUPING_OBSERVATIONS", 1)
    assert client.get(url).status_code == 409
    assert client.get(url + "/" + key).status_code == 409
    monkeypatch.setattr(projection, "MAX_GROUPING_OBSERVATIONS", 5000)
    monkeypatch.setattr(policy, "MAX_FIELD_CLAIMS", 1)
    assert client.get(url).status_code == 409
    monkeypatch.setattr(policy, "MAX_FIELD_CLAIMS", 250)
    monkeypatch.setattr(policy, "MAX_FIELD_CANDIDATES", 1)
    assert client.get(url).status_code == 409
    # A selected normal field remains accessible without building unrelated candidate graphs.
    normal = client.get(url + "?kind=all&field=act_arr_time")
    assert normal.status_code == 200 and normal.json()["total"] == 2


@pytest.mark.parametrize("corruption", ["version", "count", "issues"])
def test_inconsistent_persisted_state_is_not_silently_returned_or_exposed(client, corruption):
    job_id, _ = dataset(client)
    url = f"/api/v1/flights/jobs/{job_id}/discrepancies"
    with Session(engine) as session:
        if corruption == "version":
            metadata = session.get(JobImport, job_id)
            metadata.options = {"contract_version": 999}
            session.add(metadata)
        elif corruption == "count":
            job = session.get(ProcessingJob, job_id)
            job.total_rows += 1
            session.add(job)
        else:
            row = session.get(FlightObservation, (job_id, "one"))
            row.issues = [{"private-diagnostic-value": "never expose"}]
            session.add(row)
        session.commit()
    response = client.get(url)
    assert response.status_code == 409 and "discrepancies" not in response.json()
    assert "private-diagnostic-value" not in response.text and "never expose" not in response.text
