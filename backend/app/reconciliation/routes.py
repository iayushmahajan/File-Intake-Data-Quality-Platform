"""Bounded read-only investigation projections. No evidence or decision persistence."""

from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core.db import get_session
from app.reconciliation.evidence import (
    Baseline, EvidenceFlags, FieldEvidence, StatusCounts, investigate_field, investigation_id,
)
from app.reconciliation.grouping import GroupedFlights, TIME_FIELDS, TimeField
from app.reconciliation.observations import load_grouped_flights

router = APIRouter(prefix="/api/v1/flights/jobs", tags=["flight discrepancies"])
DiscrepancyKind = Literal["attention", "conflict", "uncertain", "missing", "all"]


@dataclass(frozen=True)
class DiscrepancySummary:
    discrepancy_id: str
    flight: str
    field: TimeField
    observation_count: int
    usable_source_count: int
    candidate_count: int
    counts: StatusCounts
    flags: EvidenceFlags
    baseline: Baseline
    requires_attention: bool
    summary: str
    evidence_digest: str
    detection_policy: str
    normalization_policy: str


@dataclass(frozen=True)
class DiscrepancyPage:
    job_id: int
    discrepancies: tuple[DiscrepancySummary, ...]
    total: int
    page: int
    page_size: int
    ungroupable_observation_count: int
    raw_observations_url: str


def _read_fields(
    session: Session, job_id: int, *, field: TimeField | None = None,
    discrepancy_id: str | None = None,
) -> tuple[GroupedFlights, tuple[FieldEvidence, ...]]:
    try:
        grouped = load_grouped_flights(session, job_id)
        evidence = tuple(investigate_field(group, name)
                         for group in grouped.groups for name in TIME_FIELDS
                         if (field is None or name == field) and (
                             discrepancy_id is None or
                             investigation_id(group.job_id, group.flight, name) == discrepancy_id
                         ))
        return grouped, evidence
    except ValueError as error:
        # The loader/domain ValueErrors are deliberate, constant public diagnostics.
        raise HTTPException(409, str(error)) from error
    except (TypeError, AttributeError, KeyError) as error:
        # Malformed stored issues/claims must not leak their values or diagnostics.
        raise HTTPException(409, "Stored Flights observation state is inconsistent.") from error
    except LookupError as error:
        raise HTTPException(404, "Job not found.") from error
    except SQLAlchemyError as error:
        raise HTTPException(503, "Flights evidence storage is unavailable.") from error


def _matches(evidence: FieldEvidence, kind: DiscrepancyKind) -> bool:
    flags = evidence.flags
    if kind == "all":
        return True
    if kind == "conflict":
        return flags.confirmed_conflict
    if kind == "missing":
        return flags.has_missing or flags.has_placeholders
    if kind == "uncertain":
        return any((flags.has_ambiguous, flags.has_unsupported,
                    flags.incomparable_supported_values, flags.unusable_source_identity,
                    flags.internal_source_conflict, flags.insufficient_support))
    return evidence.requires_attention


@router.get("/{job_id}/discrepancies", response_model=DiscrepancyPage)
def list_discrepancies(
    job_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    kind: DiscrepancyKind = "attention",
    field: TimeField | None = None,
    session: Session = Depends(get_session),
):
    grouped, fields = _read_fields(session, job_id, field=field)
    selected = [item for item in fields if (field is None or item.field == field) and _matches(item, kind)]
    summaries = tuple(DiscrepancySummary(
        discrepancy_id=item.discrepancy_id, flight=item.flight, field=item.field,
        observation_count=item.observation_count, usable_source_count=item.usable_source_count,
        candidate_count=len(item.candidates), counts=item.counts, flags=item.flags,
        baseline=item.baseline, requires_attention=item.requires_attention,
        summary=item.summary, evidence_digest=item.evidence_digest,
        detection_policy=item.detection_policy, normalization_policy=item.normalization_policy,
    ) for item in selected[(page - 1) * page_size:page * page_size])
    return DiscrepancyPage(job_id, summaries, len(selected), page, page_size,
                           len(grouped.ungroupable), f"/api/v1/flights/jobs/{job_id}/observations")


@router.get("/{job_id}/discrepancies/{discrepancy_id}", response_model=FieldEvidence)
def get_discrepancy(
    job_id: int,
    discrepancy_id: str = Path(min_length=1, max_length=80),
    session: Session = Depends(get_session),
):
    _, fields = _read_fields(session, job_id, discrepancy_id=discrepancy_id)
    for item in fields:
        if item.discrepancy_id == discrepancy_id:
            return item
    raise HTTPException(404, "Discrepancy not found in this job snapshot.")
