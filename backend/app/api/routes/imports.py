import csv
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import update
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.processing_job import ImportTemplate
from app.intake.schemas import ImportOptions, TemplateWrite
from app.services.import_config import inspect_csv
from app.utils.file_io import save_upload_file

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


def parse_options(value):
    try:
        return ImportOptions.model_validate_json(value) if value else ImportOptions()
    except ValidationError as error:
        raise HTTPException(422, "; ".join(e["msg"] for e in error.errors())) from error


def resolve_options(options, session):
    if options.template_id:
        template = session.get(ImportTemplate, options.template_id)
        if not template or template.version != options.template_version:
            raise HTTPException(
                409,
                "Template changed or no longer exists. Reload templates and preview again.",
            )
        saved = ImportOptions.model_validate(template.options)
        if saved.mapping != options.mapping or saved.rules != options.rules:
            raise HTTPException(
                422,
                "Modified settings must be saved as a template version or used without a template.",
            )
    return options


@router.post("/preview")
def preview(
    file: UploadFile = File(...),
    import_options: str | None = Form(None),
    session: Session = Depends(get_session),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are allowed.")
    options = (
        resolve_options(parse_options(import_options), session)
        if import_options
        else None
    )
    _, path = save_upload_file(file)
    try:
        return inspect_csv(path, options)
    except (ValueError, UnicodeError, csv.Error) as error:
        raise HTTPException(422, str(error)) from error
    finally:
        path.unlink(missing_ok=True)


@router.get("/templates")
def templates(session: Session = Depends(get_session)):
    return session.exec(
        select(ImportTemplate).order_by(ImportTemplate.name, ImportTemplate.id)
    ).all()


@router.post("/templates", status_code=201)
def save_template(body: TemplateWrite, session: Session = Depends(get_session)):
    name = body.name.strip()
    if not name or not body.options.mapping:
        raise HTTPException(422, "A template requires a name and a complete mapping.")
    options = body.options.model_copy(
        update={"template_id": None, "template_version": None}
    )
    template = ImportTemplate(name=name, options=options.model_dump())
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


@router.put("/templates/{template_id}")
def update_template(
    template_id: int, body: TemplateWrite, session: Session = Depends(get_session)
):
    if (
        not body.name.strip()
        or not body.options.mapping
        or body.expected_version is None
    ):
        raise HTTPException(
            422, "Name, complete mapping and expected version are required."
        )
    options = body.options.model_copy(
        update={"template_id": None, "template_version": None}
    )
    result = session.exec(
        update(ImportTemplate)
        .where(
            ImportTemplate.id == template_id,
            ImportTemplate.version == body.expected_version,
        )
        .values(
            name=body.name.strip(),
            options=options.model_dump(),
            version=ImportTemplate.version + 1,
            updated_at=datetime.utcnow(),
        )
    )
    if result.rowcount != 1:
        session.rollback()
        raise HTTPException(
            409, "Template changed or no longer exists. Reload before saving."
        )
    session.commit()
    return session.get(ImportTemplate, template_id)
