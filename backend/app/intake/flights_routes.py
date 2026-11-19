"""Flights-only upload and read APIs; legacy transaction contracts stay separate."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.core.db import get_session
from app.intake.flights import (
    FLIGHTS_CONTRACT, FlightObservationData, FlightsImportError, IntakeIssue,
    file_sha256, reject_reference_hash,
)
from app.jobs.schemas import JobStatus, UploadResponse
from app.jobs.service import create_job, get_job_or_404
from app.models.processing_job import FlightObservation, JobAnalysis, JobExecution, JobImport, ProcessingJob
from app.utils.file_io import save_upload_file

router = APIRouter(prefix="/api/v1/flights", tags=["flights"])


class FlightsJobResponse(BaseModel):
    id: int
    job_kind: Literal["raha_flights_v1"]
    contract_version: int
    status: JobStatus
    filename_original: str
    filename_input_saved: str
    input_sha256: str
    file_size: int
    created_at: datetime
    processed_at: datetime | None
    attempts: int
    duration_ms: int
    observation_count: int
    observations_available: bool
    issues: list[IntakeIssue]
    error_message: str | None


class FlightObservationPage(BaseModel):
    job_id: int
    observations: list[FlightObservationData]
    total: int
    page: int
    page_size: int


def require_flights(job_id: int, session: Session):
    job = get_job_or_404(job_id, session)
    if job.job_kind != FLIGHTS_CONTRACT:
        raise HTTPException(409, "This job is not a raha_flights_v1 import.")
    return job


@router.post("/uploads", response_model=UploadResponse, status_code=202)
def upload_flights(
    response: Response,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are allowed.")
    filename, path = save_upload_file(file)
    # Cleanup only before durable acceptance; preserve ambiguous commit handling in create_job.
    try:
        digest = file_sha256(path)
        reject_reference_hash(digest)
    except FlightsImportError as error:
        path.unlink(missing_ok=True)
        raise HTTPException(422, error.issue.model_dump()) from error
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return create_job(
        session, response, file.filename.replace("\\", "/").split("/")[-1],
        filename, path, None, job_kind=FLIGHTS_CONTRACT, input_sha256=digest,
    )


class FlightsJobSummary(BaseModel):
    id: int
    job_kind: Literal["raha_flights_v1"]
    contract_version: int | None
    status: JobStatus
    filename_original: str
    created_at: datetime
    processed_at: datetime | None
    file_size: int | None
    observation_count: int
    error_message: str | None


class FlightsJobPage(BaseModel):
    jobs: list[FlightsJobSummary]
    total: int
    page: int
    page_size: int


@router.get("/jobs", response_model=FlightsJobPage)
def list_flights_jobs(
    page: int = Query(1, ge=1, le=2147483647),
    page_size: int = Query(15, ge=1, le=100),
    status: JobStatus | None = None,
    session: Session = Depends(get_session),
):
    filters = [ProcessingJob.job_kind == FLIGHTS_CONTRACT]
    if status is not None:
        filters.append(ProcessingJob.status == status)
    try:
        total = session.exec(select(func.count()).select_from(ProcessingJob).where(*filters)).one()
        rows = session.exec(
            select(ProcessingJob, JobImport, JobAnalysis)
            .outerjoin(JobImport, JobImport.job_id == ProcessingJob.id)
            .outerjoin(JobAnalysis, JobAnalysis.job_id == ProcessingJob.id)
            .where(*filters).order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
    except SQLAlchemyError as error:
        raise HTTPException(503, "Flights history storage is unavailable.") from error
    return FlightsJobPage(jobs=[FlightsJobSummary(
        id=job.id, job_kind=job.job_kind, status=job.status,
        contract_version=metadata.options.get("contract_version") if metadata and isinstance(metadata.options, dict) else None,
        filename_original=job.filename_original, created_at=job.created_at,
        processed_at=job.processed_at if job.status in {"completed", "failed"} else None,
        file_size=metrics.file_size if metrics else None, observation_count=job.total_rows,
        error_message=job.error_message,
    ) for job, metadata, metrics in rows], total=total, page=page, page_size=page_size)


@router.get("/jobs/{job_id}", response_model=FlightsJobResponse)
def get_flights_job(job_id: int, session: Session = Depends(get_session)):
    job = require_flights(job_id, session)
    metadata = session.get(JobImport, job_id)
    metrics = session.get(JobAnalysis, job_id)
    execution = session.get(JobExecution, job_id)
    return FlightsJobResponse(
        **job.model_dump(), contract_version=metadata.options["contract_version"],
        file_size=metrics.file_size, duration_ms=metrics.duration_ms,
        attempts=execution.attempts, observation_count=job.total_rows,
        observations_available=job.status == "completed", issues=metadata.issues,
    ).model_copy(update={
        "processed_at": job.processed_at if job.status in {"completed", "failed"} else None,
    })


@router.get("/jobs/{job_id}/observations", response_model=FlightObservationPage)
def get_flight_observations(
    job_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
):
    job = require_flights(job_id, session)
    if job.status != "completed":
        raise HTTPException(409, "Observations are available only for completed Flights imports.")
    observations = session.exec(
        select(FlightObservation).where(FlightObservation.job_id == job_id)
        .order_by(FlightObservation.row_number)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return FlightObservationPage(
        job_id=job_id, observations=[FlightObservationData.model_validate(row) for row in observations],
        total=job.total_rows, page=page, page_size=page_size,
    )
