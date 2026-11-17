"""Add Flights job identity and immutable source observations; retain legacy data."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # The adoption path may encounter a jobs table created from current metadata.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("processing_jobs")}
    if "job_kind" not in columns:
        op.add_column("processing_jobs", sa.Column(
            "job_kind", sa.String(), nullable=False, server_default="transactions"
        ))
    if "input_sha256" not in columns:
        op.add_column("processing_jobs", sa.Column("input_sha256", sa.String(), nullable=True))
    op.add_column("job_imports", sa.Column(
        "issues", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
    ))
    op.create_table(
        "flight_observations",
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("processing_jobs.id"), primary_key=True),
        sa.Column("tuple_id", sa.String(1024), primary_key=True),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("src", sa.Text(), nullable=False),
        sa.Column("flight", sa.Text(), nullable=False),
        sa.Column("sched_dep_time", sa.Text(), nullable=False),
        sa.Column("act_dep_time", sa.Text(), nullable=False),
        sa.Column("sched_arr_time", sa.Text(), nullable=False),
        sa.Column("act_arr_time", sa.Text(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.UniqueConstraint("job_id", "row_number", name="uq_flight_observation_position"),
        sa.CheckConstraint("row_number >= 2", name="ck_flight_observation_position"),
    )


def downgrade():
    raise RuntimeError("Destructive downgrade is disabled; restore a reviewed backup.")
