"""Local reviewer decisions and frozen export API; no AI calls."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from app.reconciliation import review, reviewed_exports as exports

router = APIRouter(prefix="/api/v1/flights/jobs", tags=["flight human review"])
ReviewState = Literal["unreviewed", "accepted", "overridden", "rejected", "unresolved"]


class Resolution(BaseModel):
    origin: Literal["observed_candidate", "human_assertion"]
    canonical_clock: str
    precision: Literal["minute", "second"]
    qualifiers: list[str]
    supporting_observation_ids: list[str]
    supporting_source_ids: list[str]


class DecisionEvent(BaseModel):
    id: str
    request_id: str
    job_id: int
    discrepancy_id: str
    flight: str
    field: Literal["sched_dep_time", "act_dep_time", "sched_arr_time", "act_arr_time"]
    evidence_digest: str
    revision: int
    action: Literal["accept", "override", "reject", "unresolved"]
    candidate_id: str | None
    investigation_id: str | None
    manual_value: str | None
    resolution: Resolution | None
    rationale: str
    reviewer_label: str
    policy_version: str
    normalization_policy: str
    detection_policy: str
    created_at: datetime


class CurrentReview(BaseModel):
    job_id: int
    discrepancy_id: str
    evidence_digest: str
    state: ReviewState
    stale: bool
    revision: int
    decision: DecisionEvent | None
    resolution: Resolution | None
    reviewer_identity_verified: Literal[False]


class DecisionHistory(BaseModel):
    events: list[DecisionEvent]
    total: int
    page: int
    page_size: int


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_snapshot_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")


class ExportSnapshot(BaseModel):
    job_id: int
    snapshot_digest: str
    field_count: int
    ungroupable_observation_count: int


class Artifact(BaseModel):
    sha256: str
    bytes: int


class ReviewedExport(BaseModel):
    id: str
    request_id: str
    job_id: int
    snapshot_digest: str
    input_sha256: str
    policy_version: str
    artifacts: dict[str, Artifact]
    created_at: datetime


class ExportPage(BaseModel):
    exports: list[ReviewedExport]
    total: int
    page: int
    page_size: int


def storage_error(error):
    if isinstance(error, SQLAlchemyError):
        return HTTPException(503, "Review/export storage is unavailable. Retry writes with the same request identifier.")
    return HTTPException(503, "Export filesystem is unavailable; no successful export was returned.")


@router.get("/{job_id}/discrepancies/{discrepancy_id}/review", response_model=CurrentReview)
def current_review(job_id: int, discrepancy_id: str = Path(min_length=1, max_length=80)):
    try:
        return review.get_review(job_id, discrepancy_id)
    except SQLAlchemyError as error:
        raise storage_error(error) from error


@router.post("/{job_id}/discrepancies/{discrepancy_id}/review", response_model=DecisionEvent)
def decide(job_id: int, body: review.ReviewRequest, discrepancy_id: str = Path(min_length=1, max_length=80)):
    try:
        return review.submit_review(job_id, discrepancy_id, body)
    except SQLAlchemyError as error:
        raise storage_error(error) from error


@router.get("/{job_id}/discrepancies/{discrepancy_id}/review/history", response_model=DecisionHistory)
def decision_history(
    job_id: int, discrepancy_id: str = Path(min_length=1, max_length=80),
    page: int = Query(1, ge=1, le=2147483647), page_size: int = Query(25, ge=1, le=100),
):
    try:
        return review.history(job_id, discrepancy_id, page, page_size)
    except SQLAlchemyError as error:
        raise storage_error(error) from error


@router.get("/{job_id}/exports/snapshot", response_model=ExportSnapshot)
def export_snapshot(job_id: int):
    try:
        snapshot, checksum = exports.capture_snapshot(job_id)
        return dict(job_id=job_id, snapshot_digest=checksum, field_count=len(snapshot["fields"]),
                    ungroupable_observation_count=len(snapshot["ungroupable_observations"]))
    except SQLAlchemyError as error:
        raise storage_error(error) from error


@router.post("/{job_id}/exports", response_model=ReviewedExport)
def freeze_export(job_id: int, body: ExportRequest):
    try:
        return exports.create_export(job_id, body.expected_snapshot_digest, body.request_id)
    except (SQLAlchemyError, OSError) as error:
        raise storage_error(error) from error


@router.get("/{job_id}/exports", response_model=ExportPage)
def export_list(job_id: int, page: int = Query(1, ge=1, le=2147483647), page_size: int = Query(25, ge=1, le=100)):
    try:
        return exports.list_exports(job_id, page, page_size)
    except SQLAlchemyError as error:
        raise storage_error(error) from error


@router.get("/{job_id}/exports/{export_id}", response_model=ReviewedExport)
def export_detail(job_id: int, export_id: str = Path(pattern=r"^[0-9a-f]{32}$")):
    try:
        return exports.get_export(job_id, export_id)
    except SQLAlchemyError as error:
        raise storage_error(error) from error


@router.get("/{job_id}/exports/{export_id}/download/{artifact}")
def export_download(
    job_id: int, export_id: str = Path(pattern=r"^[0-9a-f]{32}$"),
    artifact: Literal["reviewed", "exceptions", "provenance"] = "reviewed",
):
    try:
        content = exports.artifact_bytes(job_id, export_id, artifact)
    except (SQLAlchemyError, OSError) as error:
        raise storage_error(error) from error
    filename = exports.ARTIFACTS[artifact]
    return Response(content, media_type="application/json" if artifact == "provenance" else "text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{export_id}-{filename}"',
                             "X-Content-Type-Options": "nosniff"})
