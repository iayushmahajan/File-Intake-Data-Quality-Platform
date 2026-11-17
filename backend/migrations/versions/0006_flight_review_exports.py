"""Append-only human review and frozen export metadata; no existing data rewrite."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "flight_review_decisions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("processing_jobs.id"), nullable=False),
        *[sa.Column(name, sa.String(), nullable=False) for name in (
            "request_id", "request_fingerprint", "discrepancy_id", "field", "evidence_digest",
            "action", "rationale", "reviewer_label", "policy_version", "normalization_policy", "detection_policy")],
        sa.Column("flight", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.String(), nullable=True),
        sa.Column("investigation_id", sa.String(), sa.ForeignKey("flight_investigations.id"), nullable=True),
        sa.Column("manual_value", sa.Text(), nullable=True),
        sa.Column("resolution", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_id", name="uq_review_request"),
        sa.UniqueConstraint("job_id", "discrepancy_id", "revision", name="uq_review_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_review_revision"),
        sa.CheckConstraint("action IN ('accept', 'override', 'reject', 'unresolved')", name="ck_review_action"),
    )
    op.create_table(
        "flight_reviewed_exports",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("processing_jobs.id"), nullable=False),
        *[sa.Column(name, sa.String(), nullable=False) for name in (
            "request_id", "request_fingerprint", "snapshot_digest", "input_sha256", "policy_version")],
        sa.Column("artifacts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_id", name="uq_reviewed_export_request"),
    )
    op.create_index("ix_reviewed_export_job_created", "flight_reviewed_exports", ["job_id", "created_at", "id"])


def downgrade():
    raise RuntimeError("Destructive downgrade is disabled; restore a reviewed backup.")
