from datetime import datetime
from pathlib import Path
from typing import Literal

from app.analytics.schemas import AIReport, AnalysisResponse
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

JobStatus = Literal["pending", "queued", "processing", "completed", "failed"]


class UploadResponse(BaseModel):
    status: JobStatus
    error_message: str | None = None
    message: str
    original_filename: str
    saved_filename: str
    job_id: int
    status_url: str


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename_original: str
    filename_input_saved: str
    filename_cleaned: str
    filename_error_report: str
    status: JobStatus
    total_rows: int
    valid_rows: int
    invalid_rows: int
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None

    @field_serializer("filename_cleaned", "filename_error_report")
    def public_output_name(self, value: str) -> str:
        # Downloads resolve storage paths server-side using the job ID.
        # Attempt tokens and directory organization are internal details.
        return Path(value).name if value else ""

    @model_validator(mode="after")
    def hide_unfinished_timestamp(self):
        if self.status in {"pending", "queued", "processing"}:
            self.processed_at = None
        return self


class JobListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int


class JobDetailResponse(JobResponse):
    records_available: bool = False
    parent_job_id: int | None = None
    parent_summary: dict | None = None
    child_job_ids: list[int] = Field(default_factory=list)
    import_options: dict | None = None
    corrections: dict = Field(default_factory=dict)
    attempts: int = 0
    file_size: int | None = None
    duration_ms: int | None = None
    analysis: AnalysisResponse | None = None
    error_breakdown: dict[str, int] = Field(default_factory=dict)
    ai_report: AIReport | None = None
