"""Complete conservative projections and immutable three-artifact snapshots."""

import csv
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import OUTPUT_DIR
from app.core.db import engine
from app.models.processing_job import FlightReviewDecision, FlightReviewedExport, ProcessingJob
from app.reconciliation.ai import digest, encode
from app.reconciliation.evidence import DETECTION_POLICY, investigate_field
from app.reconciliation.grouping import TIME_FIELDS
from app.reconciliation.normalization import NORMALIZATION_POLICY
from app.reconciliation.observations import load_grouped_flights
from app.reconciliation.review import REVIEW_POLICY, decision_data, effective_review, lock_review_job

EXPORT_POLICY = "flight_reviewed_export_v1"
MAX_EXPORT_BYTES = 32 * 1024 * 1024
MAX_FIELDS = 20000
ARTIFACTS = {"reviewed": "reviewed.csv", "exceptions": "exceptions.csv", "provenance": "provenance.json"}
REVIEWED_COLUMNS = ["job_id", "export_id", "flight", *[
    column for field in TIME_FIELDS for column in (field, field + "_status", field + "_decision_id", field + "_revision")]]
EXCEPTION_COLUMNS = ["job_id", "export_id", "flight", "field", "discrepancy_id", "review_status", "reason",
                     "decision_id", "revision", "tuple_id", "src", "row_number"]


def capture_snapshot(job_id, *, session=None):
    with (Session(engine) if session is None else nullcontext(session)) as session:
        try:
            grouped = load_grouped_flights(session, job_id)
            job = session.get(ProcessingJob, job_id)
            if not job.input_sha256 or not re.fullmatch(r"[0-9a-f]{64}", job.input_sha256):
                raise ValueError("Source file hash is unavailable or inconsistent.")
            fields = [investigate_field(group, field) for group in grouped.groups for field in TIME_FIELDS]
            if len(fields) > MAX_FIELDS:
                raise ValueError("Review snapshot exceeds the bounded field limit.")
            # One SQL statement captures a coherent latest revision vector, rather than
            # reading one field at a time while concurrent reviews may commit.
            maxima = select(FlightReviewDecision.discrepancy_id.label("scope"),
                            func.max(FlightReviewDecision.revision).label("revision")).where(
                FlightReviewDecision.job_id == job_id).group_by(FlightReviewDecision.discrepancy_id).subquery()
            events = session.exec(select(FlightReviewDecision).join(maxima, and_(
                FlightReviewDecision.discrepancy_id == maxima.c.scope,
                FlightReviewDecision.revision == maxima.c.revision,
            )).where(FlightReviewDecision.job_id == job_id).order_by(FlightReviewDecision.discrepancy_id)
                                  .limit(MAX_FIELDS + 1)).all()
            if len(events) > MAX_FIELDS:
                raise ValueError("Review snapshot exceeds the bounded field limit.")
            indexed = {event.discrepancy_id: event for event in events}
            entries = []
            for evidence in fields:
                event = indexed.get(evidence.discrepancy_id)
                status, resolution = effective_review(evidence, event)
                entries.append(dict(
                    discrepancy_id=evidence.discrepancy_id, flight=evidence.flight, field=evidence.field,
                    evidence_digest=evidence.evidence_digest, status=status, resolution=resolution,
                    decision=decision_data(event) if event else None,
                    observations=[dict(tuple_id=c.tuple_id, src=c.src, row_number=c.row_number,
                                       source_usable=c.source_usable) for c in evidence.claims],
                ))
            ungroupable = [dict(tuple_id=item.observation.raw.tuple_id, src=item.observation.raw.src,
                                flight=item.observation.raw.flight, row_number=item.observation.raw.row_number,
                                reason=item.reason, fields=list(TIME_FIELDS),
                                issues=[asdict(i) for i in item.observation.raw.issues]) for item in grouped.ungroupable]
            included = {field.discrepancy_id for field in fields}
            snapshot = dict(job_id=job_id, input_sha256=job.input_sha256, contract="raha_flights_v1", contract_version=1,
                            export_policy=EXPORT_POLICY, review_policy=REVIEW_POLICY,
                            normalization_policy=NORMALIZATION_POLICY, detection_policy=DETECTION_POLICY,
                            fields=entries, ungroupable_observations=ungroupable,
                            unmapped_decisions=[decision_data(event) for event in events if event.discrepancy_id not in included])
            # Convert timestamps once so hashing and manifest serialization agree.
            snapshot = json.loads(json.dumps(snapshot, default=lambda value: value.isoformat(), ensure_ascii=False))
            return snapshot, "sha256:" + digest(snapshot)
        except LookupError as error:
            raise HTTPException(404, "Job not found.") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        except (TypeError, AttributeError, KeyError) as error:
            raise HTTPException(409, "Stored Flights snapshot is inconsistent.") from error


def spreadsheet_cell(value):
    """Reversible presentation: escape dangerous text AND original apostrophe prefixes."""
    if isinstance(value, str) and value and (
        value.startswith("'") or value[:1] in "=+-@" or value != value.lstrip() or
        any(ord(c) < 32 for c in value) or value.startswith("\ufeff")
    ):
        return "'" + value
    return value


def csv_content(columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: spreadsheet_cell(value) for key, value in row.items()})
    return stream.getvalue().encode("utf-8")


def artifact_info(data):
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def render_snapshot(snapshot, snapshot_digest, export_id, generated_at):
    """Pure rendering: fixed snapshot + identity/time produces identical bytes."""
    flights, exceptions = {}, []
    for entry in snapshot["fields"]:
        flight = entry["flight"]
        row = flights.setdefault(flight, dict(job_id=snapshot["job_id"], export_id=export_id, flight=flight))
        field, decision = entry["field"], entry["decision"]
        revision = decision["revision"] if decision else 0
        decision_id = decision["id"] if decision else ""
        row.update({field: entry["resolution"]["canonical_clock"] if entry["resolution"] else "",
                    field + "_status": entry["status"], field + "_decision_id": decision_id,
                    field + "_revision": revision})
        if not entry["resolution"]:
            exceptions.append(dict(job_id=snapshot["job_id"], export_id=export_id, flight=flight, field=field,
                                   discrepancy_id=entry["discrepancy_id"], review_status=entry["status"],
                                   reason="stale_review" if entry["status"] == "stale" else "no_human_approved_value",
                                   decision_id=decision_id, revision=revision, tuple_id="", src="", row_number=""))
    for item in snapshot["ungroupable_observations"]:
        exceptions.append(dict(job_id=snapshot["job_id"], export_id=export_id, flight=item["flight"], field="",
                               discrepancy_id="", review_status="ungroupable", reason=item["reason"],
                               decision_id="", revision=0, tuple_id=item["tuple_id"], src=item["src"], row_number=item["row_number"]))
    data = {"reviewed": csv_content(REVIEWED_COLUMNS, [flights[key] for key in sorted(flights)]),
            "exceptions": csv_content(EXCEPTION_COLUMNS, exceptions)}
    manifest = dict(export_id=export_id, generated_at=generated_at, snapshot_digest=snapshot_digest,
                    snapshot=snapshot, artifacts={key: artifact_info(value) for key, value in data.items()},
                    csv_presentation="Prefix one apostrophe for dangerous strings or original leading apostrophes; remove one leading apostrophe to recover. JSON identities are exact.",
                    resolution_policy="Only current accepted/overridden human decisions produce values. All other fields are empty.",
                    evaluation_unit="Project each approved entity/field value to its listed job/tuple_id/field observation cells; unresolved and ungroupable cells remain unapproved.",
                    reviewer_identity="Local labels, not authenticated identities.")
    data["provenance"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if sum(len(value) for value in data.values()) > MAX_EXPORT_BYTES:
        raise HTTPException(413, "Complete export exceeds the 32 MiB artifact budget; nothing was truncated.")
    return data


def export_root():
    root = OUTPUT_DIR / "flight-reviewed"
    if not root.resolve().is_relative_to(OUTPUT_DIR.resolve()) or root.is_symlink():
        raise HTTPException(409, "Export storage root is inconsistent.")
    return root


def write_artifacts(export_id, data):
    root = export_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary, final = root / (".pending-" + export_id), root / export_id
    temporary.mkdir(mode=0o700)
    try:
        for key, content in data.items():
            with (temporary / ARTIFACTS[key]).open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        # The generated UUID owns this namespace. Never replace an existing export.
        if final.exists():
            raise FileExistsError()
        temporary.rename(final)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return final


def export_data(record):
    if not isinstance(record.artifacts, dict) or set(record.artifacts) != set(ARTIFACTS):
        raise HTTPException(409, "Export artifact metadata is inconsistent.")
    for info in record.artifacts.values():
        if (not isinstance(info, dict) or type(info.get("bytes")) is not int or
                not 0 <= info["bytes"] <= MAX_EXPORT_BYTES or
                not isinstance(info.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", info["sha256"])):
            raise HTTPException(409, "Export artifact metadata is inconsistent.")
    return record.model_dump(exclude={"request_fingerprint"})


def _replay(session, job_id, request_id, fingerprint):
    record = session.exec(select(FlightReviewedExport).where(FlightReviewedExport.request_id == request_id)).first()
    if record and (record.job_id != job_id or record.request_fingerprint != fingerprint):
        raise HTTPException(409, "Export request identifier was reused with a different payload.")
    return record


def create_export(job_id, expected_snapshot_digest, request_id):
    fingerprint = digest([job_id, expected_snapshot_digest, request_id])
    with Session(engine) as session:
        replay = _replay(session, job_id, request_id, fingerprint)
        if replay:
            return export_data(replay)
    snapshot, snapshot_digest = capture_snapshot(job_id)
    if snapshot_digest != expected_snapshot_digest:
        raise HTTPException(409, "Export snapshot changed. Refresh the snapshot before exporting.")
    identifier, now = uuid4().hex, datetime.utcnow()
    data = render_snapshot(snapshot, snapshot_digest, identifier, now.isoformat())
    final = write_artifacts(identifier, data)
    record = FlightReviewedExport(
        id=identifier, request_id=request_id, request_fingerprint=fingerprint, job_id=job_id,
        snapshot_digest=snapshot_digest, input_sha256=snapshot["input_sha256"], policy_version=EXPORT_POLICY,
        artifacts={key: artifact_info(value) for key, value in data.items()}, created_at=now)
    with Session(engine) as session:
        try:
            # The same job lock guards all review writes. Revalidation and metadata
            # commit are atomic relative to them; artifact generation held no lock.
            lock_review_job(session, job_id)
            _, refreshed = capture_snapshot(job_id, session=session)
            if refreshed != snapshot_digest:
                raise HTTPException(409, "Reviews or evidence changed during export generation. Refresh and retry.")
        except BaseException:
            shutil.rmtree(final, ignore_errors=True)  # No metadata write attempted.
            raise
        session.add(record)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            replay = _replay(session, job_id, request_id, fingerprint)
            if not replay:
                raise
            # Our unique artifacts cannot belong to the winning metadata row.
            shutil.rmtree(final, ignore_errors=True)
            return export_data(replay)
        # On ambiguous commit/storage acknowledgement failure retain complete orphan
        # artifacts: deleting here might remove an authoritative committed snapshot.
        session.refresh(record)
        return export_data(record)


def get_export(job_id, export_id):
    with Session(engine) as session:
        record = session.get(FlightReviewedExport, export_id)
        if not record or record.job_id != job_id:
            raise HTTPException(404, "Reviewed export not found in this job.")
        return export_data(record)


def list_exports(job_id, page, page_size):
    with Session(engine) as session:
        job = session.get(ProcessingJob, job_id)
        if not job:
            raise HTTPException(404, "Job not found.")
        if job.job_kind != "raha_flights_v1":
            raise HTTPException(409, "Reviewed exports require a Flights job.")
        total = session.exec(select(func.count()).select_from(FlightReviewedExport).where(FlightReviewedExport.job_id == job_id)).one()
        records = session.exec(select(FlightReviewedExport).where(FlightReviewedExport.job_id == job_id)
                               .order_by(FlightReviewedExport.created_at.desc(), FlightReviewedExport.id)
                               .offset((page - 1) * page_size).limit(page_size)).all()
        return dict(exports=[export_data(record) for record in records], total=total, page=page, page_size=page_size)


def artifact_bytes(job_id, export_id, artifact):
    metadata = get_export(job_id, export_id)
    if not re.fullmatch(r"[0-9a-f]{32}", export_id) or artifact not in ARTIFACTS:
        raise HTTPException(404, "Export artifact not found.")
    root = export_root().resolve()
    directory = root / export_id
    path = directory / ARTIFACTS[artifact]
    if directory.is_symlink() or path.is_symlink() or path.resolve().parent != directory or not path.is_file():
        raise HTTPException(404, "Export artifact is unavailable.")
    expected = metadata["artifacts"].get(artifact)
    if not isinstance(expected, dict) or type(expected.get("bytes")) is not int or not 0 <= expected["bytes"] <= MAX_EXPORT_BYTES:
        raise HTTPException(409, "Export artifact metadata is inconsistent.")
    with path.open("rb") as stream:
        content = stream.read(MAX_EXPORT_BYTES + 1)
    if artifact_info(content) != expected:
        raise HTTPException(409, "Export artifact integrity check failed.")
    return content
