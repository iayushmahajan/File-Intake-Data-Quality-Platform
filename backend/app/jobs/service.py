from pathlib import Path

from app.models.processing_job import (
    JobAnalysis,
    JobExecution,
    JobImport,
    ProcessingJob,
)
from app.intake.schemas import ImportOptions
from app.intake.flights import FLIGHTS_CONTRACT, FLIGHTS_VERSION
from app.jobs.schemas import UploadResponse
from fastapi import HTTPException, Response
from sqlmodel import Session


def create_job(
    session: Session,
    response: Response,
    original: str,
    filename: str,
    path: Path,
    options: ImportOptions | None,
    parent_job_id=None,
    corrections=None,
    changes=None,
    *,
    job_kind: str = "transactions",
    input_sha256: str | None = None,
):
    if job_kind == FLIGHTS_CONTRACT:
        if options is not None or not input_sha256 or parent_job_id is not None:
            raise ValueError("Flights jobs require a hash and no transaction configuration")
        configuration = {"contract_version": FLIGHTS_VERSION}
    elif job_kind == "transactions" and options is not None:
        configuration = options.model_dump()
    else:
        raise ValueError("Unsupported job configuration")
    job = ProcessingJob(
        job_kind=job_kind,
        input_sha256=input_sha256,
        filename_original=original,
        filename_input_saved=filename,
        filename_cleaned="",
        filename_error_report="",
        status="pending",
    )
    committing = False
    try:
        session.add(job)
        session.flush()
        session.add(JobAnalysis(job_id=job.id, file_size=path.stat().st_size))
        session.add(JobExecution(job_id=job.id))
        session.add(
            JobImport(
                job_id=job.id,
                parent_job_id=parent_job_id,
                options=configuration,
                corrections=corrections or {},
                changes=changes or {},
            )
        )
        committing = True
        session.commit()
    except Exception:
        session.rollback()
        if not committing:
            path.unlink(missing_ok=True)
        raise
    session.refresh(job)
    status_url = (
        f"/api/v1/flights/jobs/{job.id}" if job_kind == FLIGHTS_CONTRACT
        else f"/api/v1/jobs/{job.id}"
    )
    response.headers["Location"] = status_url
    return UploadResponse(
        status="pending",
        message="Upload accepted for background processing.",
        original_filename=original,
        saved_filename=filename,
        job_id=job.id,
        status_url=status_url,
    )


def get_job_or_404(job_id: int, session: Session) -> ProcessingJob:
    job = session.get(ProcessingJob, job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    return job
