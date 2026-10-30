"""Paginated record inspection and immutable correction submissions."""

import csv
import io
import json
import shutil
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.routes.jobs import get_job_or_404
from app.core.config import INPUT_DIR, MAX_UPLOAD_BYTES
from app.core.db import engine, get_session
from app.models.processing_job import JobImport, JobRecord
from app.intake.schemas import REQUIRED_COLUMNS, ImportOptions
from app.records.schemas import CorrectionRequest, RecordPage, RecordResponse
from app.schemas.job import UploadResponse
from app.services.import_config import row_errors, structured_issues
from app.services.job_creation import create_job

router = APIRouter(prefix="/api/v1/jobs", tags=["records"])


def require_records(job_id, session):
    job = get_job_or_404(job_id, session)
    metadata = session.get(JobImport, job_id)
    if job.status != "completed" or not metadata or not metadata.records_available:
        raise HTTPException(
            409,
            "Record exploration is available for completed jobs processed with the current importer. Upload the file again to index older results.",
        )
    return job, metadata


def record_filters(
    status: Literal["all", "accepted", "rejected"] = "all",
    search: str = Query("", max_length=200),
    category: str = Query("", max_length=80),
    sort: str = Query("row_number", max_length=30),
    direction: Literal["asc", "desc"] = "asc",
):
    if sort not in ["row_number", "status", *REQUIRED_COLUMNS]:
        raise HTTPException(422, "Unknown sort column")
    return dict(
        status=status, search=search, category=category, sort=sort, direction=direction
    )


def record_statement(job_id, filters):
    statement = select(JobRecord).where(JobRecord.job_id == job_id)
    if filters["status"] != "all":
        statement = statement.where(JobRecord.status == filters["status"])
    if filters["search"].strip():
        statement = statement.where(
            JobRecord.search_text.contains(
                filters["search"].strip().casefold(), autoescape=True
            )
        )
    if filters["category"]:
        statement = statement.where(
            JobRecord.categories.contains(
                "|" + filters["category"] + "|", autoescape=True
            )
        )
    key = filters["sort"]
    column = (
        getattr(JobRecord, key)
        if key in {"row_number", "status"}
        else JobRecord.values[key].as_string()
    )
    return statement.order_by(
        column.desc() if filters["direction"] == "desc" else column.asc(),
        JobRecord.row_number,
    )


def public_record(record):
    return RecordResponse(**record.model_dump())


@router.get("/{job_id}/records", response_model=RecordPage)
def records(
    job_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    filters: dict = Depends(record_filters),
    session: Session = Depends(get_session),
):
    require_records(job_id, session)
    statement = record_statement(job_id, filters)
    total = session.exec(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).one()
    rows = session.exec(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return RecordPage(
        records=[public_record(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        fields=REQUIRED_COLUMNS,
    )


@router.get("/{job_id}/records/export")
def export_records(
    job_id: int,
    filters: dict = Depends(record_filters),
    session: Session = Depends(get_session),
):
    require_records(job_id, session)
    statement = record_statement(job_id, filters)

    def generate():
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["row_number", "status", *REQUIRED_COLUMNS, "errors"])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        offset = 0
        while True:
            # Results are immutable; bounded pages avoid holding all exports in RAM.
            with Session(engine) as own_session:
                batch = own_session.exec(statement.offset(offset).limit(500)).all()
            if not batch:
                break
            for row in batch:
                writer.writerow(
                    [
                        row.row_number,
                        row.status,
                        *[row.values.get(k, "") for k in REQUIRED_COLUMNS],
                        "; ".join(i["message"] for i in row.issues),
                    ]
                )
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            offset += len(batch)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="job-{job_id}-filtered.csv"'
        },
    )


def correction_data(job_id, body, session):
    job, metadata = require_records(job_id, session)
    options = ImportOptions.model_validate(metadata.options)
    patches = {}
    changes = {}
    previews = []
    rows = session.exec(
        select(JobRecord).where(
            JobRecord.job_id == job_id, JobRecord.row_number.in_(list(body.patches))
        )
    ).all()
    indexed = {row.row_number: row for row in rows}
    for row_number, values in body.patches.items():
        record = indexed.get(row_number)
        if not record or record.status != "rejected":
            raise HTTPException(
                422, f"Record {row_number} is not a rejected record in this job."
            )
        if any(i["category"] == "CSV Structure" for i in record.issues):
            raise HTTPException(
                422,
                f"Record {row_number} has a column-count error. Correct the source file and upload again.",
            )
        delta = {k: v for k, v in values.items() if v != record.values.get(k, "")}
        if not delta:
            continue
        merged = {**record.values, **delta}
        errors, _ = row_errors(merged, row_number, options)
        patches[str(row_number)] = delta
        changes[str(row_number)] = {
            k: {"before": record.values.get(k, ""), "after": v}
            for k, v in delta.items()
        }
        previews.append(
            {
                "row_number": row_number,
                "values": merged,
                "issues": structured_issues(errors),
            }
        )
    if not patches:
        raise HTTPException(422, "No changed values to submit.")
    return job, metadata, options, patches, changes, previews


@router.post("/{job_id}/corrections/validate")
def validate_corrections(
    job_id: int, body: CorrectionRequest, session: Session = Depends(get_session)
):
    *_, previews = correction_data(job_id, body, session)
    return {
        "rows": previews,
        "valid": all(not row["issues"] for row in previews),
        "message": "Field checks only. Duplicate detection and overall quality are recalculated across the full file during reprocessing.",
    }


@router.post("/{job_id}/corrections", response_model=UploadResponse, status_code=202)
def reprocess(
    job_id: int,
    body: CorrectionRequest,
    response: Response,
    session: Session = Depends(get_session),
):
    job, metadata, options, patches, changes, previews = correction_data(
        job_id, body, session
    )
    if any(row["issues"] for row in previews):
        raise HTTPException(
            422, "Correct the field validation errors before reprocessing."
        )
    cumulative = {k: dict(v) for k, v in metadata.corrections.items()}
    for row, values in patches.items():
        cumulative[row] = {**cumulative.get(row, {}), **values}
    if len(json.dumps(cumulative).encode()) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            413, "Combined corrections exceed the configured input limit."
        )
    source = (INPUT_DIR / job.filename_input_saved).resolve()
    if not source.is_relative_to(INPUT_DIR.resolve()) or not source.is_file():
        raise HTTPException(404, "Original input file is unavailable.")
    filename = f"{uuid4().hex}_correction.csv"
    path = INPUT_DIR / filename
    try:
        with source.open("rb") as reader, path.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return create_job(
        session,
        response,
        job.filename_original,
        filename,
        path,
        options,
        parent_job_id=job_id,
        corrections=cumulative,
        changes=changes,
    )
