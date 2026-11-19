"""Synthetic Flights imports through the real durable service and isolated DB/files."""

import ast
import csv
from datetime import datetime, timedelta
import errno
import hashlib
import io
from pathlib import Path
from threading import Event
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql.dml import Insert
from sqlmodel import Session, select

from app.core.config import INPUT_DIR
from app.core.db import engine, get_session
from app.intake import flights_routes
from app.intake.flights import (
    EVALUATION_REFERENCE_SHA256, FLIGHTS_CONTRACT, FLIGHTS_FIELDS,
    file_sha256, process_flights_file, reject_reference_hash, FlightsImportError,
)
from app.main import app
from app.models.processing_job import (
    FlightObservation, JobExecution, JobImport, JobRecord, ProcessingJob,
)
from app.services import job_processing
from app.services.dispatch import dispatch_once, recover_expired
from app.services.job_processing import claim_job, process_job
from app.tasks import process_job_task
from test_uploads import VALID_CSV


def observation(key="opaque-001", src="source-a", flight="ZZ-1-AAA-BBB", value="08:00"):
    return [key, src, flight, value, "", "Not Available", "09:00 p.m. (Estimated)"]


def csv_bytes(rows=None, header=FLIGHTS_FIELDS):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(header)
    writer.writerows(rows if rows is not None else [observation()])
    return stream.getvalue().encode("utf-8")


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def submit(client, content=None):
    response = client.post("/api/v1/flights/uploads", files={
        "file": ("observations.csv", content if content is not None else csv_bytes(), "text/csv"),
    })
    assert response.status_code == 202, response.text
    assert response.headers["location"] == response.json()["status_url"]
    return response.json()["job_id"]


def detail(client, job_id):
    response = client.get(f"/api/v1/flights/jobs/{job_id}")
    assert response.status_code == 200, response.text
    return response.json()


def observation_count(job_id):
    with Session(engine) as session:
        return session.exec(select(func.count()).select_from(FlightObservation).where(
            FlightObservation.job_id == job_id
        )).one()


def test_durable_acceptance_raw_preservation_and_duplicate_delivery(client):
    raw = observation("not-an-integer-λ", src="source-α", value=' 07:00, "unusual"\r\n未定 ')
    content = b"\xef\xbb\xbf" + csv_bytes([raw, observation("second-id")])
    job_id = submit(client, content)
    pending = detail(client, job_id)
    assert pending["job_kind"] == FLIGHTS_CONTRACT
    assert pending["contract_version"] == 1
    assert pending["status"] == "pending" and pending["processed_at"] is None
    assert pending["input_sha256"] == hashlib.sha256(content).hexdigest()
    assert pending["file_size"] == len(content)
    assert pending["observation_count"] == 0 and not pending["observations_available"]
    with Session(engine) as session:
        assert session.get(JobExecution, job_id).claim_token is None
        assert session.get(JobImport, job_id).options == {"contract_version": 1}
    assert (INPUT_DIR / pending["filename_input_saved"]).read_bytes() == content
    assert client.get(f"/api/v1/flights/jobs/{job_id}/observations").status_code == 409
    delivered = []
    assert dispatch_once(delivered.append) == 1 and delivered == [job_id]
    assert detail(client, job_id)["status"] == "queued"
    assert process_job_task.apply(args=[job_id], throw=True).result == "completed"
    completed = detail(client, job_id)
    assert completed["observation_count"] == 2 and completed["observations_available"]
    assert completed["attempts"] == 1 and completed["processed_at"] is not None
    result = client.get(f"/api/v1/flights/jobs/{job_id}/observations").json()
    first = result["observations"][0]
    assert {field: first[field] for field in FLIGHTS_FIELDS} == dict(zip(FLIGHTS_FIELDS, raw))
    assert first["row_number"] == 2 and first["issues"] == []
    assert result["observations"][1]["row_number"] == 3  # Logical records, not physical lines.
    assert process_job_task.apply(args=[job_id], throw=True).result == "ignored"
    assert detail(client, job_id) == completed and observation_count(job_id) == 2
    assert client.get(f"/api/v1/jobs/{job_id}/download/input").content == content
    with Session(engine) as session:
        assert session.exec(select(JobRecord).where(JobRecord.job_id == job_id)).all() == []
    another_snapshot = submit(client, content)
    assert process_job(another_snapshot) == "completed"
    assert observation_count(another_snapshot) == observation_count(job_id) == 2


def test_identity_issues_are_retained_and_repeated_source_claims_not_rejected(client):
    rows = [observation("1", src="", flight=""),
            observation("2", src=" source-b ", flight="malformed"),
            observation("3"), observation("4")]
    job_id = submit(client, csv_bytes(rows))
    assert process_job(job_id) == "completed"
    saved = client.get(f"/api/v1/flights/jobs/{job_id}/observations").json()["observations"]
    for original, persisted in zip(rows, saved):
        assert [persisted[field] for field in FLIGHTS_FIELDS] == original
    assert {issue["field"] for issue in saved[0]["issues"]} == {"src", "flight"}
    assert {issue["code"] for issue in saved[1]["issues"]} == {"source_shape", "flight_shape"}
    assert len(saved) == 4  # Identical source/flight/time claims with different IDs survive.


@pytest.mark.parametrize("content,code,row_number", [
    (csv_bytes(header=FLIGHTS_FIELDS[:-1]), "header", 1),
    (csv_bytes(header=tuple(reversed(FLIGHTS_FIELDS))), "header", 1),
    (csv_bytes(header=["tuple_id"] * 7), "header", 1),
    (b"", "header", 1),
    (csv_bytes([]), "empty_dataset", None),
    (csv_bytes([observation(), observation()]), "duplicate_tuple_id", 3),
    (csv_bytes([observation(), observation(" ")]), "missing_tuple_id", 3),
    (csv_bytes([observation(), observation("2")[:-1]]), "column_count", 3),
    (csv_bytes([observation() + ["extra"]]), "column_count", 2),
    (csv_bytes([]) + b'"unclosed', "csv_structure", 2),
    # A later NUL must not reclassify an earlier quoting error.
    (csv_bytes([]) + b'"bad"quote\r\n\x00', "csv_structure", 2),
    (csv_bytes([observation(value="__NUL_BYTE__")]).replace(b"__NUL_BYTE__", b"\x00"), "null_character", 2),
    (csv_bytes([observation("x" * 1025)]), "tuple_id_size", 2),
    (b"\xff", "encoding", None),
])
def test_invalid_files_fail_without_partial_publication(client, content, code, row_number):
    if code == "null_character":
        assert content.count(b"\x00") == 1
    job_id = submit(client, content)
    assert process_job(job_id) == "failed"
    failed = detail(client, job_id)
    assert failed["issues"][0]["code"] == code
    assert failed["issues"][0]["row_number"] == row_number
    assert failed["error_message"]
    assert not failed["observations_available"] and failed["observation_count"] == 0
    assert observation_count(job_id) == 0
    assert client.get(f"/api/v1/flights/jobs/{job_id}/observations").status_code == 409
    assert client.get(f"/api/v1/jobs/{job_id}/download/input").content == content


def test_reference_hash_rejection_without_loading_reference(client, monkeypatch):
    # Test the real guard with the published digest, never load or reconstruct labels.
    with pytest.raises(FlightsImportError, match="evaluation-only"):
        reject_reference_hash(EVALUATION_REFERENCE_SHA256)
    reject_reference_hash(hashlib.sha256(csv_bytes()).hexdigest())
    before = set(INPUT_DIR.glob("*"))
    monkeypatch.setattr(flights_routes, "file_sha256", lambda _: EVALUATION_REFERENCE_SHA256)
    response = client.post("/api/v1/flights/uploads", files={"file": ("synthetic.csv", csv_bytes())})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "evaluation_reference"
    assert set(INPUT_DIR.glob("*")) == before
    with Session(engine) as session:
        assert session.exec(select(ProcessingJob)).all() == []


def test_changed_input_fails_provenance_check(client):
    job_id = submit(client)
    metadata = detail(client, job_id)
    (INPUT_DIR / metadata["filename_input_saved"]).write_bytes(csv_bytes([observation("different")]))
    assert process_job(job_id) == "failed"
    assert detail(client, job_id)["issues"][0]["code"] == "input_changed"
    assert observation_count(job_id) == 0


def test_pagination_errors_and_transaction_boundary(client):
    job_id = submit(client, csv_bytes([observation(str(i)) for i in range(105)]))
    assert process_job(job_id) == "completed"
    url = f"/api/v1/flights/jobs/{job_id}/observations"
    first = client.get(url + "?page_size=100").json()
    second = client.get(url + "?page_size=100&page=2").json()
    assert first["total"] == 105 and len(first["observations"]) == 100
    assert [r["row_number"] for r in second["observations"]] == list(range(102, 107))
    assert client.get(url + "?page=999").json()["observations"] == []
    for query in ["page=0", "page_size=0", "page_size=101", "page=abc"]:
        assert client.get(url + "?" + query).status_code == 422
    assert client.get("/api/v1/flights/jobs/999999").status_code == 404
    assert client.get("/api/v1/flights/jobs/999999/observations").status_code == 404
    transaction = client.post("/api/v1/uploads", files={"file": ("transactions.csv", VALID_CSV)}).json()["job_id"]
    assert process_job(transaction) == "completed"
    assert client.get(f"/api/v1/flights/jobs/{transaction}").status_code == 409
    assert client.get(f"/api/v1/flights/jobs/{transaction}/observations").status_code == 409
    for suffix in ["", "/records", "/records/export"]:
        assert client.get(f"/api/v1/jobs/{job_id}{suffix}").status_code == 409
    assert client.post(f"/api/v1/jobs/{job_id}/ai-analysis").status_code == 409
    assert client.post(f"/api/v1/jobs/{job_id}/corrections", json={
        "patches": {"2": {"email": "test@example.com"}},
    }).status_code == 409
    assert [r["id"] for r in client.get("/api/v1/jobs").json()["jobs"]] == [transaction]


def test_upload_request_and_size_guards(client, monkeypatch):
    assert client.post("/api/v1/flights/uploads").status_code == 422
    assert client.post("/api/v1/flights/uploads", files={"file": ("bad.txt", b"x")}).status_code == 400
    from app.utils import file_io
    monkeypatch.setattr(file_io, "MAX_UPLOAD_BYTES", 1)
    before = set(INPUT_DIR.glob("*"))
    assert client.post("/api/v1/flights/uploads", files={"file": ("big.csv", csv_bytes())}).status_code == 413
    assert set(INPUT_DIR.glob("*")) == before


def test_duplicate_concurrent_delivery_only_claims_once(client, monkeypatch):
    original = job_processing.process_flights_file
    entered, finish = Event(), Event()

    def blocked(*args):
        entered.set()
        assert finish.wait(5)
        return original(*args)

    monkeypatch.setattr(job_processing, "process_flights_file", blocked)
    job_id = submit(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        work = pool.submit(process_job, job_id)
        assert entered.wait(5)
        try:
            assert pool.submit(process_job, job_id).result(timeout=5) == "ignored"
        finally:
            finish.set()
        assert work.result(timeout=5) == "completed"
    assert observation_count(job_id) == 1 and detail(client, job_id)["attempts"] == 1


def test_expired_attempt_cannot_publish_and_recovery_uses_new_claim(client):
    job_id = submit(client)
    token, filename = claim_job(job_id)
    result = process_flights_file(INPUT_DIR / filename, file_sha256(INPUT_DIR / filename)).model_dump()
    assert job_processing._finish(job_id, "wrong-token", result, 1) is False
    with Session(engine) as session:
        execution = session.get(JobExecution, job_id)
        execution.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
        session.add(execution)
        session.commit()
    assert job_processing._finish(job_id, token, result, 1) is False
    assert observation_count(job_id) == 0
    assert recover_expired(datetime.utcnow()) == 1
    assert process_job(job_id) == "completed"
    assert job_processing._finish(job_id, token, result, 1) is False
    assert observation_count(job_id) == 1 and detail(client, job_id)["attempts"] == 2


def test_observation_insert_failure_rolls_back_entire_publication(client, monkeypatch):
    original = Session.execute
    inserts = 0

    def fail_second_batch(self, statement, *args, **kwargs):
        nonlocal inserts
        if isinstance(statement, Insert) and statement.table.name == "flight_observations":
            inserts += 1
            if inserts == 2:
                raise OperationalError("insert", {}, Exception("synthetic outage"))
        return original(self, statement, *args, **kwargs)

    job_id = submit(client, csv_bytes([observation(str(i)) for i in range(501)]))
    monkeypatch.setattr(Session, "execute", fail_second_batch)
    with pytest.raises(OperationalError):
        process_job(job_id)
    monkeypatch.setattr(Session, "execute", original)
    assert observation_count(job_id) == 0
    assert detail(client, job_id)["status"] == "processing"
    assert not detail(client, job_id)["observations_available"]
    with Session(engine) as session:
        execution = session.get(JobExecution, job_id)
        assert execution.claim_token is not None
        execution.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
        session.add(execution)
        session.commit()
    recover_expired(datetime.utcnow())
    assert process_job(job_id) == "completed"
    assert observation_count(job_id) == 501


def test_temporary_storage_failure_uses_existing_bounded_retry(client, monkeypatch):
    original = job_processing.process_flights_file
    monkeypatch.setattr(job_processing, "process_flights_file", lambda *args: (_ for _ in ()).throw(
        OSError(errno.EAGAIN, "temporary")
    ))
    job_id = submit(client)
    assert process_job(job_id) == "retrying"
    assert detail(client, job_id)["status"] == "pending" and observation_count(job_id) == 0
    monkeypatch.setattr(job_processing, "process_flights_file", original)
    assert process_job(job_id) == "completed"
    assert detail(client, job_id)["attempts"] == 2


def test_lost_completion_ack_does_not_duplicate_observations(client, monkeypatch):
    original = job_processing._finish

    def lost_ack(*args):
        original(*args)
        raise OperationalError("commit", {}, Exception("lost acknowledgement"))

    job_id = submit(client)
    monkeypatch.setattr(job_processing, "_finish", lost_ack)
    with pytest.raises(OperationalError):
        process_job(job_id)
    assert detail(client, job_id)["status"] == "completed"
    assert observation_count(job_id) == 1
    assert process_job(job_id) == "ignored"


def test_lost_acceptance_ack_preserves_input_and_work_intent(monkeypatch):
    class LostAckSession(Session):
        def commit(self):
            super().commit()
            raise OperationalError("commit", {}, Exception("lost acknowledgement"))

    def override():
        with LostAckSession(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.post("/api/v1/flights/uploads", files={
                "file": ("synthetic.csv", csv_bytes()),
            }).status_code == 500
    finally:
        app.dependency_overrides.pop(get_session, None)
    with Session(engine) as session:
        job = session.exec(select(ProcessingJob)).one()
        job_id = job.id
        assert job.job_kind == FLIGHTS_CONTRACT
        assert session.get(JobExecution, job_id) is not None
        assert (INPUT_DIR / job.filename_input_saved).is_file()
    assert process_job(job_id) == "completed" and observation_count(job_id) == 1


def test_runtime_has_no_offline_reference_dependency():
    root = Path(__file__).resolve().parents[1] / "app"
    for path in root.rglob("*.py"):
        source = path.read_text()
        tree = ast.parse(source)
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names]
        assert not any("inspect_flights" in name for name in imports)
        assert "FLIGHTS_BENCHMARK_ROOT" not in source
        assert "reference/clean.csv" not in source
