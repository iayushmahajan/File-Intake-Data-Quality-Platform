"""Explicit human decisions. No source updates or provider calls."""

from typing import Literal
from uuid import uuid4
import json

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import engine
from app.models.processing_job import FlightInvestigation, FlightReviewDecision, ProcessingJob
from app.reconciliation import ai
from app.reconciliation.investigations import configuration, read_evidence
from app.reconciliation.normalization import normalize_time

REVIEW_POLICY = "flight_human_review_v1"
STATES = {"accept": "accepted", "override": "overridden", "reject": "rejected", "unresolved": "unresolved"}


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_evidence_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_revision: int = Field(ge=0, le=2147483646)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")
    action: Literal["accept", "override", "reject", "unresolved"]
    reviewer_label: str = Field(min_length=1, max_length=80)
    rationale: str = Field(default="", max_length=1000)
    candidate_id: str | None = Field(default=None, max_length=80)
    investigation_id: str | None = Field(default=None, min_length=1, max_length=80)
    manual_value: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def action_fields(self):
        if not self.reviewer_label.strip() or any(ord(c) < 32 for c in self.reviewer_label):
            raise ValueError("Provide a local reviewer label, not an authenticated identity.")
        if any(ord(c) < 32 and c not in "\n\t" for c in self.rationale):
            raise ValueError("Invalid rationale text.")
        if self.action in ("override", "reject") and not self.rationale.strip():
            raise ValueError("A concise rationale is required.")
        if self.action in ("accept", "reject"):
            if not self.investigation_id or self.candidate_id is not None or self.manual_value is not None:
                raise ValueError("Accept/reject requires only an investigation reference.")
        elif self.action == "override":
            if (self.candidate_id is None) == (self.manual_value is None):
                raise ValueError("Select one candidate or enter one manual clock.")
        elif any(x is not None for x in (self.candidate_id, self.manual_value, self.investigation_id)):
            raise ValueError("Unresolved cannot select a value or recommendation.")
        return self


def candidate_resolution(candidate):
    return dict(origin="observed_candidate", canonical_clock=candidate.canonical_clock,
                precision=candidate.precision, qualifiers=list(candidate.qualifiers),
                supporting_observation_ids=list(candidate.supporting_observation_ids),
                supporting_source_ids=list(candidate.supporting_source_ids))


def manual_resolution(value):
    normalized = normalize_time(value)
    if normalized.status != "parsed":
        raise HTTPException(422, "Manual replacement requires an explicit supported clock under normalization v1.")
    return dict(origin="human_assertion", canonical_clock=normalized.canonical_clock,
                precision=normalized.precision, qualifiers=list(normalized.qualifiers),
                supporting_observation_ids=[], supporting_source_ids=[])


def validate_action(body, evidence, session):
    candidates = {c.candidate_id: c for c in evidence.candidates}
    selected = None
    if body.investigation_id:
        investigation = session.get(FlightInvestigation, body.investigation_id)
        if (not investigation or investigation.job_id != evidence.job_id or
                investigation.discrepancy_id != evidence.discrepancy_id or
                investigation.evidence_digest != evidence.evidence_digest or
                investigation.config_fingerprint != configuration()[2] or investigation.status != "proposed"):
            raise HTTPException(409, "Investigation must be a current validated proposal for this discrepancy.")
        try:
            recommendation = ai.validate_recommendation(
                json.dumps(investigation.result), evidence, ai.prepare_evidence(evidence))
            if recommendation.recommendation != "propose":
                raise ai.InvestigationProblem("invalid_response")
            selected = recommendation.candidate_id
        except (ai.InvestigationProblem, TypeError, ValueError) as error:
            raise HTTPException(409, "Stored AI proposal is invalid for the current evidence.") from error
    if body.action == "reject":
        return selected, None
    if body.action == "unresolved":
        return None, None
    if body.action == "override":
        if body.manual_value is not None:
            return None, manual_resolution(body.manual_value)
        selected = body.candidate_id
    if selected not in candidates:
        raise HTTPException(422, "Candidate does not belong to the current discrepancy evidence.")
    return selected, candidate_resolution(candidates[selected])


def lock_review_job(session, job_id):
    """Short publication gate shared by review inserts and export commits.

    Row locking on PostgreSQL; SQLite's equivalent is a short write reservation.
    No existing job column is changed. Files/provider requests stay outside it.
    """
    if session.get_bind().dialect.name == "sqlite":
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    job = session.exec(select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()).first()
    if not job:
        raise HTTPException(404, "Job not found.")
    if job.job_kind != "raha_flights_v1" or job.status != "completed":
        raise HTTPException(409, "Human review/export requires a completed Flights job.")


def latest_decision(session, job_id, discrepancy_id):
    return session.exec(select(FlightReviewDecision).where(
        FlightReviewDecision.job_id == job_id, FlightReviewDecision.discrepancy_id == discrepancy_id,
    ).order_by(FlightReviewDecision.revision.desc()).limit(1)).first()


def decision_data(event):
    return event.model_dump(exclude={"request_fingerprint"})


def submit_review(job_id: int, discrepancy_id: str, body: ReviewRequest):
    fingerprint = ai.digest([job_id, discrepancy_id, body.model_dump()])
    with Session(engine) as session:
        prior = session.exec(select(FlightReviewDecision).where(FlightReviewDecision.request_id == body.request_id)).first()
        if prior:
            if prior.request_fingerprint != fingerprint:
                raise HTTPException(409, "Review request identifier was reused with a different payload.")
            return decision_data(prior)
    evidence = read_evidence(job_id, discrepancy_id)
    if evidence.evidence_digest != body.expected_evidence_digest:
        raise HTTPException(409, "Evidence changed. Refresh before submitting review.")
    with Session(engine) as session:
        lock_review_job(session, job_id)
        previous = latest_decision(session, job_id, discrepancy_id)
        revision = previous.revision if previous else 0
        if body.expected_revision != revision:
            # A concurrent exact request can commit after our first replay lookup.
            prior = session.exec(select(FlightReviewDecision).where(FlightReviewDecision.request_id == body.request_id)).first()
            if prior and prior.request_fingerprint == fingerprint:
                return decision_data(prior)
            raise HTTPException(409, "Decision revision changed. Refresh before submitting review.")
        candidate_id, resolution = validate_action(body, evidence, session)
        event = FlightReviewDecision(
            id=uuid4().hex, request_id=body.request_id, request_fingerprint=fingerprint,
            job_id=job_id, discrepancy_id=discrepancy_id, flight=evidence.flight, field=evidence.field,
            evidence_digest=evidence.evidence_digest, revision=revision + 1, action=body.action,
            candidate_id=candidate_id, investigation_id=body.investigation_id, manual_value=body.manual_value,
            resolution=resolution, rationale=body.rationale, reviewer_label=body.reviewer_label,
            policy_version=REVIEW_POLICY, normalization_policy=evidence.normalization_policy,
            detection_policy=evidence.detection_policy,
        )
        session.add(event)
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            prior = session.exec(select(FlightReviewDecision).where(FlightReviewDecision.request_id == body.request_id)).first()
            if prior and prior.request_fingerprint == fingerprint:
                return decision_data(prior)
            raise HTTPException(409, "Concurrent decision or conflicting request identifier. Refresh the review.") from error
        session.refresh(event)
        return decision_data(event)


def effective_review(evidence, event):
    if not event:
        return "unreviewed", None
    if event.evidence_digest != evidence.evidence_digest:
        return "stale", None
    if (event.flight != evidence.flight or event.field != evidence.field or
            event.job_id != evidence.job_id or event.discrepancy_id != evidence.discrepancy_id or
            event.normalization_policy != evidence.normalization_policy or
            event.detection_policy != evidence.detection_policy or event.policy_version != REVIEW_POLICY):
        raise HTTPException(409, "Stored review identity or policy is inconsistent.")
    if event.action not in STATES:
        raise HTTPException(409, "Stored review action is inconsistent.")
    if event.action in ("accept", "override"):
        if event.manual_value is not None:
            if event.action != "override" or event.candidate_id is not None:
                raise HTTPException(409, "Stored manual review is inconsistent.")
            try:
                expected = manual_resolution(event.manual_value)
            except HTTPException as error:
                raise HTTPException(409, "Stored manual review is inconsistent.") from error
        else:
            candidate = next((c for c in evidence.candidates if c.candidate_id == event.candidate_id), None)
            if not candidate:
                raise HTTPException(409, "Stored reviewed candidate is inconsistent.")
            expected = candidate_resolution(candidate)
        if event.resolution != expected:
            raise HTTPException(409, "Stored reviewed value or provenance is inconsistent.")
        return STATES[event.action], expected
    if event.resolution is not None:
        raise HTTPException(409, "Unapproved review cannot contain an effective value.")
    return STATES[event.action], None


def get_review(job_id, discrepancy_id):
    evidence = read_evidence(job_id, discrepancy_id)
    with Session(engine) as session:
        event = latest_decision(session, job_id, discrepancy_id)
        status, resolution = effective_review(evidence, event)
        return dict(job_id=job_id, discrepancy_id=discrepancy_id, evidence_digest=evidence.evidence_digest,
                    state="unreviewed" if status == "stale" else status, stale=status == "stale",
                    revision=event.revision if event else 0, decision=decision_data(event) if event else None,
                    resolution=resolution, reviewer_identity_verified=False)


def history(job_id, discrepancy_id, page, page_size):
    read_evidence(job_id, discrepancy_id)
    with Session(engine) as session:
        scope = (FlightReviewDecision.job_id == job_id, FlightReviewDecision.discrepancy_id == discrepancy_id)
        total = session.exec(select(func.count()).select_from(FlightReviewDecision).where(*scope)).one()
        events = session.exec(select(FlightReviewDecision).where(*scope).order_by(FlightReviewDecision.revision)
                              .offset((page - 1) * page_size).limit(page_size)).all()
        return dict(events=[decision_data(e) for e in events], total=total, page=page, page_size=page_size)
