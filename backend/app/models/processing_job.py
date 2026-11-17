from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, Column, Index, String, Text, UniqueConstraint, text
from sqlmodel import Field, SQLModel


class ProcessingJob(SQLModel, table=True):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        Index("ix_jobs_created_at", "created_at", "id"),
        Index("ix_jobs_status", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_kind: str = Field(
        default="transactions",
        sa_column=Column(String, nullable=False, server_default="transactions"),
    )
    input_sha256: str | None = Field(default=None)
    filename_original: str
    filename_input_saved: str
    filename_cleaned: str
    filename_error_report: str
    status: str = Field(default="pending")
    total_rows: int = Field(default=0)
    valid_rows: int = Field(default=0)
    invalid_rows: int = Field(default=0)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class JobAnalysis(SQLModel, table=True):
    """Additive table: historical job rows remain intact and readable."""

    __tablename__ = "job_analyses"
    job_id: int = Field(primary_key=True, foreign_key="processing_jobs.id")
    file_size: int = 0
    duration_ms: int = 0
    analysis: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error_breakdown: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    ai_report: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))


class JobExecution(SQLModel, table=True):
    """Durable work intent and fenced execution lease; no Celery result backend."""

    __tablename__ = "job_executions"
    __table_args__ = (Index("ix_execution_next_dispatch", "next_dispatch_at"),)
    job_id: int = Field(primary_key=True, foreign_key="processing_jobs.id")
    attempts: int = 0
    publish_failures: int = 0
    claim_token: str | None = None
    lease_expires_at: datetime | None = None
    next_dispatch_at: datetime = Field(default_factory=datetime.utcnow)
    waiting_since: datetime = Field(default_factory=datetime.utcnow)


class ImportTemplate(SQLModel, table=True):
    __tablename__ = "import_templates"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    version: int = 1
    options: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobImport(SQLModel, table=True):
    __tablename__ = "job_imports"
    job_id: int = Field(primary_key=True, foreign_key="processing_jobs.id")
    parent_job_id: int | None = Field(
        default=None, foreign_key="processing_jobs.id", index=True
    )
    options: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    corrections: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    changes: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    records_available: bool = False
    issues: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class JobRecord(SQLModel, table=True):
    __tablename__ = "job_records"
    __table_args__ = (
        Index("ix_records_job_status_row", "job_id", "status", "row_number"),
    )
    job_id: int = Field(primary_key=True, foreign_key="processing_jobs.id")
    row_number: int = Field(primary_key=True)
    status: str
    values: dict = Field(sa_column=Column(JSON, nullable=False))
    normalized: dict = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    issues: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    categories: str = ""
    search_text: str = ""


class FlightObservation(SQLModel, table=True):
    """Original claims: inserted only by fenced publication; no edit API."""

    __tablename__ = "flight_observations"
    __table_args__ = (
        UniqueConstraint("job_id", "row_number", name="uq_flight_observation_position"),
        CheckConstraint("row_number >= 2", name="ck_flight_observation_position"),
    )
    job_id: int = Field(primary_key=True, foreign_key="processing_jobs.id")
    tuple_id: str = Field(sa_column=Column(String(1024), primary_key=True, nullable=False))
    row_number: int
    src: str = Field(sa_column=Column(Text, nullable=False))
    flight: str = Field(sa_column=Column(Text, nullable=False))
    sched_dep_time: str = Field(sa_column=Column(Text, nullable=False))
    act_dep_time: str = Field(sa_column=Column(Text, nullable=False))
    sched_arr_time: str = Field(sa_column=Column(Text, nullable=False))
    act_arr_time: str = Field(sa_column=Column(Text, nullable=False))
    issues: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class FlightInvestigation(SQLModel, table=True):
    """AI history only; slot and token fence bounded external requests."""

    __tablename__ = "flight_investigations"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_investigation_request"),
        UniqueConstraint("slot", name="uq_investigation_slot"),
        CheckConstraint(
            "(status = 'running' AND slot IS NOT NULL AND slot IN (0, 1) AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'running' AND slot IS NULL AND claim_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_investigation_claim",
        ),
        CheckConstraint("attempt_number BETWEEN 0 AND 3", name="ck_investigation_attempt"),
        Index("ix_investigation_scope", "job_id", "discrepancy_id", "created_at"),
        Index("uq_investigation_running", "job_id", "discrepancy_id", unique=True,
              sqlite_where=text("status = 'running'"),
              postgresql_where=text("status = 'running'")),
        Index("uq_investigation_attempt", "job_id", "discrepancy_id", "evidence_digest",
              "config_fingerprint", "attempt_number", unique=True,
              sqlite_where=text("provider_attempted = true"),
              postgresql_where=text("provider_attempted = true")),
    )
    id: str = Field(primary_key=True)
    request_id: str
    job_id: int = Field(foreign_key="processing_jobs.id")
    discrepancy_id: str
    evidence_digest: str
    config_fingerprint: str
    status: str
    slot: int | None = None
    claim_token: str | None = None
    lease_expires_at: datetime | None = None
    provider_attempted: bool = False
    attempt_number: int = 0
    provider: str | None = None
    model: str | None = None
    resolved_model: str | None = None
    response_id: str | None = None
    policy_version: str
    prompt_version: str
    schema_version: str
    payload_sha256: str | None = None
    input_bytes: int | None = None
    result: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    usage: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error_code: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class FlightReviewDecision(SQLModel, table=True):
    """Append-only local reviewer assertions; current state is the greatest revision."""

    __tablename__ = "flight_review_decisions"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_review_request"),
        UniqueConstraint("job_id", "discrepancy_id", "revision", name="uq_review_revision"),
        CheckConstraint("revision >= 1", name="ck_review_revision"),
        CheckConstraint("action IN ('accept', 'override', 'reject', 'unresolved')", name="ck_review_action"),
    )
    id: str = Field(primary_key=True)
    request_id: str
    request_fingerprint: str
    job_id: int = Field(foreign_key="processing_jobs.id")
    discrepancy_id: str
    flight: str = Field(sa_column=Column(Text, nullable=False))
    field: str
    evidence_digest: str
    revision: int
    action: str
    candidate_id: str | None = None
    investigation_id: str | None = Field(default=None, foreign_key="flight_investigations.id")
    manual_value: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    resolution: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    rationale: str
    reviewer_label: str
    policy_version: str
    normalization_policy: str
    detection_policy: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FlightReviewedExport(SQLModel, table=True):
    """Only complete frozen artifacts are published; paths are server-derived."""

    __tablename__ = "flight_reviewed_exports"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_reviewed_export_request"),
        Index("ix_reviewed_export_job_created", "job_id", "created_at", "id"),
    )
    id: str = Field(primary_key=True)
    request_id: str
    request_fingerprint: str
    job_id: int = Field(foreign_key="processing_jobs.id")
    snapshot_digest: str
    input_sha256: str
    policy_version: str
    artifacts: dict = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow)
