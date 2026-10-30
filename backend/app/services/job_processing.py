"""Fenced job execution shared by the worker and isolated service tests."""

import csv
import errno
import shutil
from datetime import datetime, timedelta
from time import perf_counter
from uuid import uuid4

from app.core.config import INPUT_DIR, JOB_LEASE_SECONDS, JOB_MAX_ATTEMPTS, OUTPUT_DIR
from app.core.db import engine
from app.core.logging import get_logger
from app.models.processing_job import (
    JobAnalysis,
    JobExecution,
    JobImport,
    JobRecord,
    ProcessingJob,
)
from app.schemas.analysis import AnalysisResponse
from app.intake.schemas import ImportOptions
from app.services.csv_processor import process_csv_file
from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy import insert, update
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

logger = get_logger(__name__)


def claim_job(job_id: int) -> tuple[str, str] | None:
    now = datetime.utcnow()
    token = uuid4().hex
    with Session(engine) as session:
        # The execution row is the only lock/claim authority. Atomic CAS works
        # on PostgreSQL and SQLite; no connection stays open during CSV work.
        claimed = session.exec(
            update(JobExecution)
            .where(
                JobExecution.job_id == job_id,
                JobExecution.claim_token.is_(None),
                JobExecution.attempts < JOB_MAX_ATTEMPTS,
            )
            .values(
                claim_token=token,
                lease_expires_at=now + timedelta(seconds=JOB_LEASE_SECONDS),
                attempts=JobExecution.attempts + 1,
            )
        )
        if claimed.rowcount != 1:
            session.rollback()
            return None
        job = session.get(ProcessingJob, job_id)
        if job is None or job.status not in {"pending", "queued"}:
            session.rollback()
            return None
        job.status = "processing"
        job.error_message = None
        session.add(job)
        filename = job.filename_input_saved
        session.commit()
    return token, filename


def _finish(job_id: int, token: str, result: dict, duration_ms: int) -> bool:
    now = datetime.utcnow()
    with Session(engine) as session:
        # Fencing: a worker whose lease expired cannot publish stale results.
        claimed = session.exec(
            update(JobExecution)
            .where(
                JobExecution.job_id == job_id,
                JobExecution.claim_token == token,
                JobExecution.lease_expires_at > now,
            )
            .values(claim_token=None, lease_expires_at=None)
        )
        if claimed.rowcount != 1:
            session.rollback()
            return False
        job = session.get(ProcessingJob, job_id)
        job.status = result["status"]
        job.error_message = result.get("error_message")
        job.processed_at = now
        job.total_rows = result["total_rows"]
        job.valid_rows = result["valid_rows"]
        job.invalid_rows = result["invalid_rows"]
        job.filename_cleaned = result["cleaned_filename"]
        job.filename_error_report = result["error_filename"]
        metrics = session.get(JobAnalysis, job_id)
        metrics.duration_ms = duration_ms
        metrics.analysis = result["analysis"]
        metrics.error_breakdown = result["error_breakdown"]
        metadata = session.get(JobImport, job_id)
        if metadata:
            metadata.records_available = (
                "records" in result and result["status"] == "completed"
            )
            session.add(metadata)
        records = result.get("records", [])
        for start in range(0, len(records), 500):
            session.execute(
                insert(JobRecord),
                [dict(item, job_id=job_id) for item in records[start : start + 500]],
            )
        session.add_all([job, metrics])
        session.commit()
    return True


def _release_for_retry(job_id: int, token: str) -> None:
    now = datetime.utcnow()
    with Session(engine) as session:
        released = session.exec(
            update(JobExecution)
            .where(
                JobExecution.job_id == job_id,
                JobExecution.claim_token == token,
                JobExecution.lease_expires_at > now,
            )
            .values(
                claim_token=None,
                lease_expires_at=None,
                next_dispatch_at=now + timedelta(seconds=5),
                waiting_since=now,
            )
        )
        if released.rowcount:
            job = session.get(ProcessingJob, job_id)
            execution = session.get(JobExecution, job_id)
            exhausted = execution.attempts >= JOB_MAX_ATTEMPTS
            job.status = "failed" if exhausted else "pending"
            job.error_message = (
                "Temporary processing failure exceeded the retry limit."
                if exhausted
                else "Temporary processing interruption; retrying automatically."
            )
            if exhausted:
                job.processed_at = now
            session.add(job)
            session.commit()


def process_job(job_id: object) -> str:
    if type(job_id) is not int or not 0 < job_id <= 2147483647:
        logger.warning("Rejected malformed processing task arguments")
        return "invalid"
    claim = claim_job(job_id)
    if claim is None:
        return "ignored"
    token, filename = claim
    # Each attempt owns a different directory. Even an expired worker cannot
    # overwrite the current attempt's CSVs. DB filenames publish only on commit.
    attempt_dir = OUTPUT_DIR / f"job-{job_id}" / token
    started = perf_counter()
    keep_outputs = False
    try:
        source = (INPUT_DIR / filename).resolve()
        if not source.is_relative_to(INPUT_DIR.resolve()):
            raise FileNotFoundError("Invalid stored input location")
        with Session(engine) as session:
            metadata = session.get(JobImport, job_id)
            options = (
                ImportOptions.model_validate(metadata.options)
                if metadata
                else ImportOptions()
            )
            corrections = dict(metadata.corrections) if metadata else {}
        result = process_csv_file(
            source, output_dir=attempt_dir, options=options, corrections=corrections
        )
        # Verify the analytical contract and files before terminal publication.
        AnalysisResponse.model_validate(result["analysis"])
        for key in ("cleaned_filename", "error_filename"):
            if result[key] and not (OUTPUT_DIR / result[key]).is_file():
                raise FileNotFoundError("Processing output was not generated")
        # A timeout or lost acknowledgement can interrupt final publication
        # after the DB committed. Retain files until _finish confirms whether
        # this attempt published or was superseded.
        keep_outputs = True
        keep_outputs = _finish(
            job_id, token, result, round((perf_counter() - started) * 1000)
        )
        return result["status"] if keep_outputs else "superseded"
    except (OSError, SoftTimeLimitExceeded) as error:
        if isinstance(error, SoftTimeLimitExceeded) or getattr(
            error, "errno", None
        ) in {errno.EAGAIN, errno.EBUSY, errno.EINTR, errno.ETIMEDOUT}:
            _release_for_retry(job_id, token)
            return "retrying"
        message = (
            "Input or generated output file is unavailable. Check shared storage and upload again."
            if isinstance(error, FileNotFoundError)
            else "File storage failed. Check available space and permissions."
        )
        return _fail(job_id, token, message, started)
    except (UnicodeError, csv.Error):
        return _fail(
            job_id,
            token,
            "The file must be valid UTF-8 CSV with correctly quoted fields.",
            started,
        )
    except Exception as error:
        if isinstance(error, SQLAlchemyError):
            # Commit acknowledgements can be ambiguous: retain attempt files
            # rather than deleting a possibly committed result.
            keep_outputs = True
            raise
        logger.exception("Processing job failed", extra={"job_id": job_id})
        return _fail(
            job_id,
            token,
            "Processing failed. Review the CSV format or contact the operator.",
            started,
        )
    finally:
        if not keep_outputs:
            shutil.rmtree(attempt_dir, ignore_errors=True)


def _fail(job_id: int, token: str, message: str, started: float) -> str:
    result = dict(
        status="failed",
        error_message=message,
        total_rows=0,
        valid_rows=0,
        invalid_rows=0,
        cleaned_filename="",
        error_filename="",
        analysis={},
        error_breakdown={},
    )
    return (
        "failed"
        if _finish(job_id, token, result, round((perf_counter() - started) * 1000))
        else "superseded"
    )
