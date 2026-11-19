"""Add bounded, non-authoritative AI investigation history; preserve all evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "flight_investigations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("processing_jobs.id"), nullable=False),
        *[sa.Column(name, sa.String(), nullable=False) for name in (
            "discrepancy_id", "evidence_digest", "config_fingerprint", "status",
            "policy_version", "prompt_version", "schema_version")],
        sa.Column("slot", sa.Integer(), nullable=True),
        sa.Column("claim_token", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("provider_attempted", sa.Boolean(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        *[sa.Column(name, sa.String(), nullable=True) for name in (
            "provider", "model", "resolved_model", "response_id", "payload_sha256", "error_code")],
        sa.Column("input_bytes", sa.Integer(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("request_id", name="uq_investigation_request"),
        sa.UniqueConstraint("slot", name="uq_investigation_slot"),
        sa.CheckConstraint(
            "(status = 'running' AND slot IS NOT NULL AND slot IN (0, 1) AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'running' AND slot IS NULL AND claim_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_investigation_claim"),
        sa.CheckConstraint("attempt_number BETWEEN 0 AND 3", name="ck_investigation_attempt"),
    )
    op.create_index("ix_investigation_scope", "flight_investigations", ["job_id", "discrepancy_id", "created_at"])
    op.create_index("uq_investigation_running", "flight_investigations", ["job_id", "discrepancy_id"],
                    unique=True, sqlite_where=sa.text("status = 'running'"), postgresql_where=sa.text("status = 'running'"))
    op.create_index("uq_investigation_attempt", "flight_investigations",
                    ["job_id", "discrepancy_id", "evidence_digest", "config_fingerprint", "attempt_number"],
                    unique=True, sqlite_where=sa.text("provider_attempted = true"),
                    postgresql_where=sa.text("provider_attempted = true"))


def downgrade():
    raise RuntimeError("Destructive downgrade is disabled; restore a reviewed backup.")
