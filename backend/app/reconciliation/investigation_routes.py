"""Explicit cost-incurring operations, separate from deterministic read endpoints."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from app.reconciliation import investigations
from app.reconciliation.ai import Recommendation

router = APIRouter(prefix="/api/v1/flights/jobs", tags=["flight AI investigations"])
Status = Literal["not_requested", "running", "proposed", "abstained", "unavailable", "invalid_response", "failed", "stale", "ineligible"]


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_evidence_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")


class ClaimReference(BaseModel):
    claim_id: str
    observation_id: str
    source_id: str


class InvestigationResponse(BaseModel):
    id: str
    request_id: str
    job_id: int
    discrepancy_id: str
    evidence_digest: str
    status: Status
    stored_status: Status
    current: bool
    authoritative: Literal[False]
    recommendation: Recommendation | None
    claim_references: list[ClaimReference]
    provider: str | None
    model: str | None
    resolved_model: str | None
    response_id: str | None
    usage: dict[str, int]
    error_code: str | None
    policy_version: str
    prompt_version: str
    schema_version: str
    payload_sha256: str | None
    input_bytes: int | None
    attempt_number: int
    created_at: datetime
    completed_at: datetime | None


class InvestigationLatest(BaseModel):
    status: Status
    investigation: InvestigationResponse | None


@router.post("/{job_id}/discrepancies/{discrepancy_id}/investigations", response_model=InvestigationResponse)
async def request_investigation(
    job_id: int, body: InvestigationRequest, response: Response,
    discrepancy_id: str = Path(min_length=1, max_length=80),
):
    try:
        outcome = await investigations.investigate(job_id, discrepancy_id, body.expected_evidence_digest, body.request_id)
    except SQLAlchemyError as error:
        raise HTTPException(503, "AI investigation storage is unavailable. Retry with the same request identifier.") from error
    if outcome["status"] == "running":
        response.status_code = 202
    return outcome


@router.get("/{job_id}/discrepancies/{discrepancy_id}/investigations", response_model=InvestigationLatest)
def latest_investigation(job_id: int, discrepancy_id: str = Path(min_length=1, max_length=80)):
    try:
        return investigations.retrieve(job_id, discrepancy_id)
    except SQLAlchemyError as error:
        raise HTTPException(503, "AI investigation storage is unavailable.") from error


@router.get("/{job_id}/discrepancies/{discrepancy_id}/investigations/{investigation_id}", response_model=InvestigationResponse)
def get_investigation(
    job_id: int, discrepancy_id: str = Path(min_length=1, max_length=80),
    investigation_id: str = Path(min_length=1, max_length=80),
):
    try:
        return investigations.retrieve(job_id, discrepancy_id, investigation_id)
    except SQLAlchemyError as error:
        raise HTTPException(503, "AI investigation storage is unavailable.") from error
