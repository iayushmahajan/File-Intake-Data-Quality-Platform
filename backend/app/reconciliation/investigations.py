"""Durable explicit investigations. No transaction spans an external request."""

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.db import engine
from app.models.processing_job import FlightInvestigation
from app.reconciliation import ai
from app.reconciliation.evidence import investigate_field, investigation_id
from app.reconciliation.grouping import TIME_FIELDS
from app.reconciliation.observations import load_grouped_flights


def read_evidence(job_id: int, discrepancy_id: str):
    with Session(engine) as session:
        try:
            grouped = load_grouped_flights(session, job_id)
            for group in grouped.groups:
                for field in TIME_FIELDS:
                    if investigation_id(job_id, group.flight, field) == discrepancy_id:
                        return investigate_field(group, field)
        except LookupError as error:
            raise HTTPException(404, "Job not found.") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        except (TypeError, AttributeError, KeyError) as error:
            raise HTTPException(409, "Stored Flights observation state is inconsistent.") from error
    raise HTTPException(404, "Discrepancy not found in this job snapshot.")


def configuration():
    try:
        return (*ai.provider_identity(), None if ai.OPENAI_API_KEY else "unconfigured")
    except ai.InvestigationProblem as error:
        return None, None, ai.digest([ai.AI_POLICY, "invalid_configuration"]), error.code


def _scope(job_id, discrepancy_id):
    return (FlightInvestigation.job_id == job_id,
            FlightInvestigation.discrepancy_id == discrepancy_id)


def _existing(session, job_id, discrepancy_id, evidence_digest, fingerprint, request_id):
    replay = session.exec(select(FlightInvestigation).where(FlightInvestigation.request_id == request_id)).first()
    if replay:
        if (replay.job_id, replay.discrepancy_id, replay.evidence_digest) != (job_id, discrepancy_id, evidence_digest):
            raise HTTPException(409, "Request identifier already belongs to another evidence request.")
        return replay
    cached = session.exec(select(FlightInvestigation).where(
        *_scope(job_id, discrepancy_id), FlightInvestigation.evidence_digest == evidence_digest,
        FlightInvestigation.config_fingerprint == fingerprint,
        FlightInvestigation.status.in_(["proposed", "abstained"]),
    ).order_by(FlightInvestigation.created_at.desc(), FlightInvestigation.id)).first()
    if cached:
        return cached
    running = session.exec(select(FlightInvestigation).where(
        *_scope(job_id, discrepancy_id), FlightInvestigation.status == "running",
    )).first()
    if running:
        if running.evidence_digest != evidence_digest or running.config_fingerprint != fingerprint:
            raise HTTPException(409, "An earlier evidence investigation is still running.")
        return running
    return None


def reserve(evidence, request_id, prepared, preflight_error, config):
    """Unique database slots, scope and attempt ordinals resolve cross-process races."""
    provider, model, fingerprint, _ = config
    for _ in range(6):
        now = datetime.utcnow()
        with Session(engine) as session:
            session.execute(update(FlightInvestigation).where(
                FlightInvestigation.status == "running", FlightInvestigation.lease_expires_at <= now,
            ).values(status="failed", error_code="interrupted", slot=None, claim_token=None,
                     lease_expires_at=None, completed_at=now))
            session.commit()
            existing = _existing(session, evidence.job_id, evidence.discrepancy_id,
                                 evidence.evidence_digest, fingerprint, request_id)
            if existing:
                session.expunge(existing)
                return existing, False
            scope = (*_scope(evidence.job_id, evidence.discrepancy_id),
                     FlightInvestigation.evidence_digest == evidence.evidence_digest,
                     FlightInvestigation.config_fingerprint == fingerprint)
            ordinal = session.exec(select(func.max(FlightInvestigation.attempt_number)).where(
                *scope, FlightInvestigation.provider_attempted == True,  # noqa: E712
            )).one() or 0
            error = preflight_error
            if not error and ordinal >= ai.MAX_ATTEMPTS:
                error = "attempt_budget_exceeded"
            occupied = set(session.exec(select(FlightInvestigation.slot).where(
                FlightInvestigation.status == "running")).all())
            slot = next((n for n in range(ai.MAX_CONCURRENT) if n not in occupied), None)
            if not error and slot is None:
                raise HTTPException(429, "AI investigation capacity is busy. Retry explicitly later.", headers={"Retry-After": "5"})
            record = FlightInvestigation(
                id=uuid4().hex, request_id=request_id, job_id=evidence.job_id,
                discrepancy_id=evidence.discrepancy_id, evidence_digest=evidence.evidence_digest,
                config_fingerprint=fingerprint, provider=provider, model=model,
                policy_version=ai.AI_POLICY, prompt_version=ai.PROMPT_VERSION, schema_version=ai.SCHEMA_VERSION,
                status=("ineligible" if error in ("ineligible_evidence", "evidence_budget_exceeded", "attempt_budget_exceeded")
                        else "unavailable") if error else "running",
                error_code=error, provider_attempted=not bool(error), attempt_number=0 if error else ordinal + 1,
                slot=None if error else slot, claim_token=None if error else uuid4().hex,
                lease_expires_at=None if error else now + timedelta(seconds=ai.LEASE_SECONDS),
                completed_at=now if error else None,
                payload_sha256=prepared.payload_sha256 if prepared else None,
                input_bytes=prepared.input_bytes if prepared else None,
            )
            session.add(record)
            try:
                session.commit()
                session.refresh(record)
                session.expunge(record)
                return record, not bool(error)
            except IntegrityError:
                session.rollback()
                # Another caller reserved the same request/scope/slot/ordinal. Re-read.
    raise HTTPException(409, "Concurrent investigation request; retry with the same request identifier.")


def _publish(record, status, error, result=None, provider_result=None):
    now = datetime.utcnow()
    with Session(engine) as session:
        values = dict(status=status, error_code=error, result=result,
                      slot=None, claim_token=None, lease_expires_at=None, completed_at=now)
        if provider_result:
            values.update(resolved_model=provider_result.model, response_id=provider_result.response_id,
                          usage=provider_result.usage)
        session.execute(update(FlightInvestigation).where(
            FlightInvestigation.id == record.id, FlightInvestigation.status == "running",
            FlightInvestigation.claim_token == record.claim_token,
            FlightInvestigation.lease_expires_at > now,
        ).values(**values))
        session.commit()
        current = session.get(FlightInvestigation, record.id)
        session.expunge(current)
        return current


async def investigate(job_id: int, discrepancy_id: str, expected_digest: str, request_id: str):
    evidence = read_evidence(job_id, discrepancy_id)
    if evidence.evidence_digest != expected_digest:
        raise HTTPException(409, "Evidence changed. Refresh the discrepancy before requesting AI.")
    config = configuration()
    prepared, error = None, None
    try:
        prepared = ai.prepare_evidence(evidence)
    except ai.InvestigationProblem as problem:
        error = problem.code
    error = error or config[3]
    record, claimed = reserve(evidence, request_id, prepared, error, config)
    if not claimed:
        return present(record, evidence)
    # A predecessor may complete between the cache read and our unique claim insert.
    # If it was still running, the unique scope constraint would reject our insert;
    # if it completed, this fresh post-commit read must reuse its result before paying.
    with Session(engine) as session:
        cached = session.exec(select(FlightInvestigation).where(
            *_scope(job_id, discrepancy_id), FlightInvestigation.id != record.id,
            FlightInvestigation.evidence_digest == evidence.evidence_digest,
            FlightInvestigation.config_fingerprint == config[2],
            FlightInvestigation.status.in_(["proposed", "abstained"]),
        ).order_by(FlightInvestigation.created_at.desc())).first()
        if cached:
            session.expunge(cached)
    if cached:
        current = _publish(record, cached.status, None, cached.result,
                           ai.ProviderResult("", cached.resolved_model, cached.response_id, {}))
        return present(current, read_evidence(job_id, discrepancy_id))
    result, response = None, None
    try:
        response = await ai.call_provider(prepared)
        recommendation = ai.validate_recommendation(response.content, evidence, prepared)
        result = recommendation.model_dump()
        status = "proposed" if recommendation.recommendation == "propose" else "abstained"
        error = None
    except ai.InvestigationProblem as problem:
        error = problem.code
        status = ("unavailable" if error in ("unconfigured", "invalid_configuration", "rate_limited", "provider_unavailable")
                  else "invalid_response" if error == "invalid_response" else "failed")
    except Exception:
        # Never persist an SDK/provider exception or full response/prompt.
        status, error = "failed", "provider_failure"
    try:
        latest = read_evidence(job_id, discrepancy_id)
        if latest.evidence_digest != evidence.evidence_digest or configuration()[2] != config[2]:
            status, error = "stale", "evidence_changed"
    except HTTPException:
        latest = None
        status, error = "stale", "evidence_unavailable"
    current = _publish(record, status, error, result, response)
    return present(current, latest)


def present(record, evidence):
    """GET projection never writes. Historical results are explicitly not current."""
    status, error = record.status, record.error_code
    current = evidence is not None and evidence.evidence_digest == record.evidence_digest and configuration()[2] == record.config_fingerprint
    if not current:
        status, error = "stale", "evidence_changed"
    elif status == "running" and record.lease_expires_at <= datetime.utcnow():
        status, error = "failed", "interrupted"
    references = []
    if evidence is not None and current:
        for claim in evidence.claims:
            references.append({"claim_id": "claim_" + ai.digest([evidence.discrepancy_id, evidence.evidence_digest, claim.tuple_id]),
                               "observation_id": claim.tuple_id, "source_id": claim.src})
    return dict(
        id=record.id, request_id=record.request_id, job_id=record.job_id,
        discrepancy_id=record.discrepancy_id, evidence_digest=record.evidence_digest,
        status=status, stored_status=record.status, current=current, authoritative=False,
        recommendation=record.result, claim_references=references,
        provider=record.provider, model=record.model, resolved_model=record.resolved_model,
        response_id=record.response_id, usage=record.usage, error_code=error,
        policy_version=record.policy_version, prompt_version=record.prompt_version,
        schema_version=record.schema_version, payload_sha256=record.payload_sha256,
        input_bytes=record.input_bytes, attempt_number=record.attempt_number,
        created_at=record.created_at, completed_at=record.completed_at,
    )


def retrieve(job_id, discrepancy_id, investigation_id=None):
    # A stored historical investigation remains retrievable when its evidence is no
    # longer projectable; a new request must always pass authoritative reconstruction.
    with Session(engine) as session:
        query = select(FlightInvestigation).where(*_scope(job_id, discrepancy_id))
        if investigation_id:
            query = query.where(FlightInvestigation.id == investigation_id)
        record = session.exec(query.order_by(FlightInvestigation.created_at.desc(), FlightInvestigation.id)).first()
        if record:
            session.expunge(record)
    try:
        evidence = read_evidence(job_id, discrepancy_id)
    except HTTPException:
        if not record:
            raise
        evidence = None
    if not record:
        if investigation_id:
            raise HTTPException(404, "Investigation not found in this discrepancy.")
        return {"status": "not_requested", "investigation": None}
    outcome = present(record, evidence)
    return outcome if investigation_id else {"status": outcome["status"], "investigation": outcome}
