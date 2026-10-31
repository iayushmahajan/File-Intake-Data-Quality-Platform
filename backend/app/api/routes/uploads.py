import csv

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlmodel import Session

from app.api.routes.imports import parse_options, resolve_options
from app.core.db import get_session
from app.schemas.job import UploadResponse
from app.intake.mapping import check_mapping
from app.services.job_creation import create_job
from app.utils.file_io import save_upload_file

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse, status_code=202)
def upload_csv(
    response: Response,
    file: UploadFile = File(...),
    import_options: str | None = Form(None),
    session: Session = Depends(get_session),
):
    if not file.filename:
        raise HTTPException(400, "No file provided.")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are allowed.")
    options = resolve_options(parse_options(import_options), session)
    filename, path = save_upload_file(file)
    if options.mapping:
        try:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                check_mapping(next(csv.reader(handle, strict=True), []), options)
        except (ValueError, UnicodeError, csv.Error) as error:
            path.unlink(missing_ok=True)
            raise HTTPException(422, str(error)) from error
    return create_job(
        session,
        response,
        file.filename.replace("\\", "/").split("/")[-1],
        filename,
        path,
        options,
    )
