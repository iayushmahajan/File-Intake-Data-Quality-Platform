import errno
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event
from pathlib import Path

import pytest
from app.core.config import INPUT_DIR, OUTPUT_DIR
from app.core.db import engine
from app.main import app
from app.models.processing_job import JobAnalysis, JobExecution, ProcessingJob
from app.services import job_processing
from app.services.dispatch import dispatch_once, recover_expired
from app.services.job_processing import process_job
from app.tasks import process_job_task
from fastapi.testclient import TestClient
from sqlmodel import Session
from test_uploads import VALID_CSV


def submit(client):
    response = client.post(
        "/api/v1/uploads", files={"file": ("async.csv", VALID_CSV, "text/csv")}
    )
    assert response.status_code == 202
    result = response.json()
    assert response.headers["location"] == result["status_url"]
    assert result["status"] == "pending"
    assert "task_id" not in result and "processing_summary" not in result
    return result["job_id"]


def clean_artifact(job_id):
    with Session(engine) as session:
        return OUTPUT_DIR / session.get(ProcessingJob, job_id).filename_cleaned


def detail(client, job_id):
    return client.get(f"/api/v1/jobs/{job_id}").json()


def test_acceptance_precedes_work_and_survives_app_lifespan_restart():
    with TestClient(app) as client:
        job_id = submit(client)
        assert detail(client, job_id)["status"] == "pending"
        assert detail(client, job_id)["processed_at"] is None
        with Session(engine) as session:
            assert session.get(JobExecution, job_id) is not None
            assert session.get(JobAnalysis, job_id).file_size == len(VALID_CSV)
    with TestClient(app) as client:
        published = []
        assert dispatch_once(published.append) == 1
        assert published == [job_id]
        assert detail(client, job_id)["status"] == "queued"
        assert process_job_task.apply(args=[job_id], throw=True).result == "completed"
        job = detail(client, job_id)
        assert job["status"] == "completed" and job["attempts"] == 1
        assert job["analysis"]["quality"]["score"] == 100
        assert job["processed_at"] is not None


def test_duplicate_delivery_does_not_rewrite_completed_results():
    with TestClient(app) as client:
        job_id = submit(client)
        assert process_job(job_id) == "completed"
        first = detail(client, job_id)
        artifact = clean_artifact(job_id)
        modified = artifact.stat().st_mtime_ns
        assert process_job_task.apply(args=[job_id], throw=True).result == "ignored"
        assert detail(client, job_id) == first
        assert artifact.stat().st_mtime_ns == modified


def test_simultaneous_delivery_only_one_claims(monkeypatch):
    entered, finish = Event(), Event()
    original = job_processing.process_csv_file

    def block(*args, **kwargs):
        entered.set()
        assert finish.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(job_processing, "process_csv_file", block)
    with TestClient(app) as client:
        job_id = submit(client)
        with ThreadPoolExecutor(max_workers=2) as pool:
            work = pool.submit(process_job, job_id)
            assert entered.wait(5)
            try:
                assert detail(client, job_id)["status"] == "processing"
                assert pool.submit(process_job, job_id).result(timeout=5) == "ignored"
            finally:
                finish.set()
            assert work.result(timeout=5) == "completed"
        assert detail(client, job_id)["attempts"] == 1


def test_stale_worker_cannot_publish_over_new_attempt(monkeypatch):
    original = job_processing.process_csv_file
    calls = []
    with TestClient(app) as client:
        job_id = submit(client)

        def supersede(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(result)
            if len(calls) == 1:
                with Session(engine) as session:
                    lease = session.get(JobExecution, job_id)
                    lease.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
                    session.add(lease)
                    session.commit()
                assert recover_expired(datetime.utcnow()) == 1
                assert process_job(job_id) == "completed"
            return result

        monkeypatch.setattr(job_processing, "process_csv_file", supersede)
        assert process_job(job_id) == "superseded"
        job = detail(client, job_id)
        assert job["attempts"] == 2
        assert job["filename_cleaned"] == Path(calls[1]["cleaned_filename"]).name
        assert (OUTPUT_DIR / calls[1]["cleaned_filename"]).exists()
        assert not (OUTPUT_DIR / calls[0]["cleaned_filename"]).exists()


def test_broker_failure_is_retried_and_bounded():
    def unavailable(_):
        raise ConnectionError("do not expose broker credentials")

    with TestClient(app) as client:
        job_id = submit(client)
        now = datetime.utcnow()
        for attempt in range(8):
            dispatch_once(unavailable, now + timedelta(seconds=31 * attempt))
        job = detail(client, job_id)
        assert job["status"] == "failed"
        assert "Queue publication failed" in job["error_message"]
        assert "credentials" not in job["error_message"]
        assert job["attempts"] == 0


def test_publication_ambiguous_ack_does_not_regress_completion():
    with TestClient(app) as client:
        job_id = submit(client)

        def delivered_but_ack_lost(value):
            assert process_job(value) == "completed"
            raise ConnectionError()

        dispatch_once(delivered_but_ack_lost)
        assert detail(client, job_id)["status"] == "completed"


def test_queued_work_is_republished_after_message_loss():
    with TestClient(app) as client:
        job_id = submit(client)
        now = datetime.utcnow()
        dispatch_once(lambda _: None, now)
        delivered = []
        assert dispatch_once(delivered.append, now + timedelta(seconds=31)) == 1
        assert delivered == [job_id]
        assert process_job(job_id) == "completed"


def test_missing_workers_and_exhausted_leases_fail_clearly():
    with TestClient(app) as client:
        waiting = submit(client)
        dispatch_once(lambda _: None, datetime.utcnow() + timedelta(seconds=601))
        assert detail(client, waiting)["status"] == "failed"
        job_id = submit(client)
        with Session(engine) as session:
            lease = session.get(JobExecution, job_id)
            lease.attempts = 3
            lease.claim_token = "lost-worker"
            lease.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
            job = session.get(ProcessingJob, job_id)
            job.status = "processing"
            session.add_all([lease, job])
            session.commit()
        recover_expired(datetime.utcnow())
        assert detail(client, job_id)["status"] == "failed"
        assert "retry limit" in detail(client, job_id)["error_message"]


def test_transient_io_retries_until_execution_attempts_are_exhausted(monkeypatch):
    with TestClient(app) as client:
        job_id = submit(client)

        def temporary(*args, **kwargs):
            raise OSError(errno.EAGAIN, "temporary")

        monkeypatch.setattr(job_processing, "process_csv_file", temporary)
        for _ in range(3):
            assert process_job(job_id) == "retrying"
        assert detail(client, job_id)["status"] == "failed"
        assert detail(client, job_id)["attempts"] == 3


@pytest.mark.parametrize("value", [None, True, "1", -1, 0, [], {"job_id": 1}, 2**60])
def test_malformed_task_arguments_are_rejected(value):
    assert process_job_task.apply(args=[value], throw=True).result == "invalid"


def test_missing_input_and_output_failures(monkeypatch):
    with TestClient(app) as client:
        job_id = submit(client)
        job = detail(client, job_id)
        (INPUT_DIR / job["filename_input_saved"]).unlink()
        assert process_job(job_id) == "failed"
        assert "unavailable" in detail(client, job_id)["error_message"]
        second = submit(client)
        assert process_job(second) == "completed"
        artifact = clean_artifact(second)
        artifact.unlink()
        assert client.get(f"/api/v1/jobs/{second}/download/clean").status_code == 404
        assert detail(client, second)["analysis"]["quality"]["score"] == 100


def test_ambiguous_worker_commit_retains_published_files(monkeypatch):
    from sqlalchemy.exc import OperationalError

    original = job_processing._finish

    def commit_then_disconnect(*args, **kwargs):
        original(*args, **kwargs)
        raise OperationalError("commit", {}, Exception("connection lost after commit"))

    monkeypatch.setattr(job_processing, "_finish", commit_then_disconnect)
    with TestClient(app) as client:
        job_id = submit(client)
        with pytest.raises(OperationalError):
            process_job(job_id)
        job = detail(client, job_id)
        assert job["status"] == "completed"
        assert clean_artifact(job_id).is_file()
        assert process_job(job_id) == "ignored"


def test_unexpected_processing_error_is_terminal_without_retries(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("private internal details")

    monkeypatch.setattr(job_processing, "process_csv_file", broken)
    with TestClient(app) as client:
        job_id = submit(client)
        assert process_job(job_id) == "failed"
        assert process_job(job_id) == "ignored"
        assert detail(client, job_id)["attempts"] == 1
        assert "private" not in detail(client, job_id)["error_message"]


def test_task_retries_database_connectivity_failures(monkeypatch):
    from app import tasks
    from celery.exceptions import Retry
    from sqlalchemy.exc import OperationalError

    calls = []

    def unavailable(_):
        raise OperationalError("connect", {}, Exception("unavailable"))

    def retry(**kwargs):
        calls.append(kwargs)
        raise Retry()

    monkeypatch.setattr(tasks, "process_job", unavailable)
    monkeypatch.setattr(process_job_task, "retry", retry)
    with pytest.raises(Retry):
        process_job_task.run(123)
    assert calls[0]["countdown"] == 2
    assert process_job_task.max_retries == 2


def test_public_file_names_hide_attempt_paths_and_downloads_work():
    with TestClient(app) as client:
        job_id = submit(client)
        assert process_job(job_id) == "completed"
        for job in [
            detail(client, job_id),
            client.get("/api/v1/jobs").json()["jobs"][0],
        ]:
            assert "/" not in job["filename_cleaned"]
            assert "/" not in job["filename_error_report"]
        response = client.get(f"/api/v1/jobs/{job_id}/download/clean")
        assert response.status_code == 200
        assert (
            detail(client, job_id)["filename_cleaned"]
            in response.headers["content-disposition"]
        )


def test_lost_upload_commit_ack_preserves_accepted_input(monkeypatch):
    from sqlalchemy.exc import OperationalError
    from sqlmodel import select
    from app.core.db import get_session

    class LostAckSession(Session):
        def commit(self):
            super().commit()
            raise OperationalError("commit", {}, Exception("lost acknowledgement"))

    def session_override():
        with LostAckSession(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/uploads", files={"file": ("ack.csv", VALID_CSV, "text/csv")}
            )
            assert response.status_code == 500
    finally:
        app.dependency_overrides.pop(get_session, None)
    with Session(engine) as session:
        job = session.exec(select(ProcessingJob)).one()
        job_id = job.id
        assert (INPUT_DIR / job.filename_input_saved).is_file()
        assert session.get(JobExecution, job_id) is not None
    assert process_job(job_id) == "completed"


def test_soft_timeout_after_commit_does_not_delete_published_output(monkeypatch):
    from billiard.exceptions import SoftTimeLimitExceeded

    original = job_processing._finish

    def commit_then_timeout(*args, **kwargs):
        original(*args, **kwargs)
        raise SoftTimeLimitExceeded()

    monkeypatch.setattr(job_processing, "_finish", commit_then_timeout)
    with TestClient(app) as client:
        job_id = submit(client)
        process_job(job_id)
        assert detail(client, job_id)["status"] == "completed"
        assert client.get(f"/api/v1/jobs/{job_id}/download/clean").status_code == 200
