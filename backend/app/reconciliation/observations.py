"""Bounded read-only bridge from completed Flights imports to pure grouped views."""

from sqlmodel import Session, select

from app.intake.flights import FLIGHTS_CONTRACT, FLIGHTS_VERSION
from app.models.processing_job import FlightObservation, JobImport, ProcessingJob
from app.reconciliation.grouping import (
    GroupedFlights, ObservationIssue, RawObservation, TIME_FIELDS, group_flights,
)

# A complete bounded snapshot, not partial groups masquerading as full evidence.
MAX_GROUPING_OBSERVATIONS = 5000


def load_grouped_flights(session: Session, job_id: int, *, batch_size: int = 100) -> GroupedFlights:
    """No commit/flush, derived persistence, file reads, API calls or worker changes.

    Pages by unique logical position, then returns a complete small snapshot.
    Larger snapshots fail explicitly and need a deliberate bounded-access design.
    """
    if type(batch_size) is not int or not 1 <= batch_size <= 100:
        raise ValueError("Batch size must be an integer from 1 to 100.")
    if session.new or session.dirty or session.deleted:
        raise ValueError("Use a clean session for read-only Flights projection.")
    with session.no_autoflush:
        job = session.get(ProcessingJob, job_id)
        if job is None:
            raise LookupError("Job not found.")
        if job.job_kind != FLIGHTS_CONTRACT or job.status != "completed":
            raise ValueError("Projection requires a completed raha_flights_v1 import.")
        metadata = session.get(JobImport, job_id)
        if metadata is None or metadata.options != {"contract_version": FLIGHTS_VERSION}:
            raise ValueError("Unsupported Flights contract version.")
        if not 0 < job.total_rows <= MAX_GROUPING_OBSERVATIONS:
            raise ValueError("Snapshot exceeds the grouping bound or has no observations.")
        rows = []
        after_position = 1
        while True:
            batch = session.exec(
                select(FlightObservation).where(
                    FlightObservation.job_id == job_id,
                    FlightObservation.row_number > after_position,
                ).order_by(FlightObservation.row_number).limit(batch_size)
            ).all()
            if not batch:
                break
            if len(rows) + len(batch) > MAX_GROUPING_OBSERVATIONS:
                raise ValueError("Stored observations exceed the grouping bound.")
            for observation in batch:
                rows.append(RawObservation(
                    job_id=job_id, tuple_id=observation.tuple_id,
                    row_number=observation.row_number, src=observation.src, flight=observation.flight,
                    issues=tuple(ObservationIssue(**issue) for issue in observation.issues),
                    **{field: getattr(observation, field) for field in TIME_FIELDS},
                ))
            after_position = batch[-1].row_number
        if len(rows) != job.total_rows:
            raise ValueError("Stored observations do not match the completed job count.")
    return group_flights(rows)
