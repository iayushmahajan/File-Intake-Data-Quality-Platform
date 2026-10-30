from pathlib import Path

from app.models.processing_job import (
    JobAnalysis,
    JobExecution,
    JobImport,
    ProcessingJob,
)
from app.intake.schemas import ImportOptions
from app.schemas.job import UploadResponse
from fastapi import Response
from sqlmodel import Session


def create_job(
    session: Session,
    response: Response,
    original: str,
    filename: str,
    path: Path,
    options: ImportOptions,
    parent_job_id=None,
    corrections=None,
    changes=None,
):
    job = ProcessingJob(
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
                options=options.model_dump(),
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
    status_url = f"/api/v1/jobs/{job.id}"
    response.headers["Location"] = status_url
    return UploadResponse(
        status="pending",
        message="Upload accepted for background processing.",
        original_filename=original,
        saved_filename=filename,
        job_id=job.id,
        status_url=status_url,
    )
