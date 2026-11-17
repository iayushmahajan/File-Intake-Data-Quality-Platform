from pathlib import Path

from alembic import command
from alembic.config import Config
from app.models.processing_job import ProcessingJob
from sqlalchemy import create_engine, inspect, text


def test_adoption_migration_preserves_existing_history(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    ProcessingJob.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(
            text("""INSERT INTO processing_jobs
            (id, filename_original, filename_input_saved, filename_cleaned, filename_error_report,
             status, total_rows, valid_rows, invalid_rows, created_at, processed_at)
            VALUES (42, 'legacy.csv', 'legacy.csv', 'clean.csv', 'errors.csv', 'completed', 3, 2, 1,
                    '2026-01-01', '2026-01-01')""")
        )
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        assert (
            connection.execute(
                text("SELECT total_rows FROM processing_jobs WHERE id=42")
            ).scalar()
            == 3
        )
        assert "job_analyses" in inspect(connection).get_table_names()


def test_async_migration_preserves_analytics_and_marks_legacy_interruption(tmp_path):
    from app.models.processing_job import JobAnalysis
    from sqlmodel import Session

    engine = create_engine(f"sqlite:///{tmp_path}/upgrade.db")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
    with Session(engine) as session:
        for job_id, status in [(1, "completed"), (2, "processing")]:
            # Seed the historical schema, not today's ORM (which includes 0004 columns).
            session.execute(
                text("""INSERT INTO processing_jobs
                (id, filename_original, filename_input_saved, filename_cleaned, filename_error_report,
                 status, total_rows, valid_rows, invalid_rows, created_at, processed_at)
                VALUES (:id, 'legacy.csv', 'input.csv', '', '', :status, 0, 0, 0,
                        '2026-01-01', '2026-01-01')"""),
                {"id": job_id, "status": status},
            )
        session.add(
            JobAnalysis(
                job_id=1,
                analysis={"quality": {"score": 88}},
                ai_report={"executive_summary": "Saved legacy report"},
            )
        )
        session.commit()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(engine) as session:
        assert session.get(ProcessingJob, 1).status == "completed"
        assert session.get(JobAnalysis, 1).analysis["quality"]["score"] == 88
        assert (
            session.get(JobAnalysis, 1).ai_report["executive_summary"]
            == "Saved legacy report"
        )
        assert session.get(ProcessingJob, 2).status == "failed"


def test_workspace_migration_preserves_queued_execution(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/workspace-upgrade.db")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
        connection.execute(
            text("""INSERT INTO processing_jobs
            (id, filename_original, filename_input_saved, filename_cleaned, filename_error_report,
             status, total_rows, valid_rows, invalid_rows, created_at, processed_at)
            VALUES (7, 'pending.csv', 'pending.csv', '', '', 'queued', 0, 0, 0, '2026-01-01', '2026-01-01')""")
        )
        connection.execute(
            text("""INSERT INTO job_executions
            (job_id, attempts, publish_failures, next_dispatch_at, waiting_since)
            VALUES (7, 0, 0, '2026-01-01', '2026-01-01')""")
        )
        command.upgrade(config, "head")
        assert (
            connection.execute(
                text("SELECT status FROM processing_jobs WHERE id=7")
            ).scalar()
            == "queued"
        )
        assert (
            connection.execute(
                text("SELECT attempts FROM job_executions WHERE job_id=7")
            ).scalar()
            == 0
        )
        assert {"job_imports", "job_records", "import_templates"} <= set(
            inspect(connection).get_table_names()
        )


def test_flights_migration_preserves_legacy_and_enforces_constraints(tmp_path):
    import pytest
    from sqlalchemy.exc import IntegrityError

    isolated = create_engine(f"sqlite:///{tmp_path}/flights-migration.db")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with isolated.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.commit()
        config.attributes["connection"] = connection
        command.upgrade(config, "0003")
        connection.execute(text("""INSERT INTO processing_jobs
            (id, filename_original, filename_input_saved, filename_cleaned, filename_error_report,
             status, total_rows, valid_rows, invalid_rows, created_at, processed_at)
            VALUES (42, 'legacy.csv', 'input.csv', 'output.csv', '', 'completed', 3, 2, 1,
                    '2026-01-01', '2026-01-01')"""))
        connection.execute(text("""INSERT INTO job_imports
            (job_id, options, corrections, changes, records_available)
            VALUES (42, '{}', '{}', '{}', 0)"""))
        connection.commit()
        command.upgrade(config, "head")
        connection.commit()
        old = connection.execute(text("SELECT job_kind, input_sha256, valid_rows, filename_cleaned FROM processing_jobs WHERE id=42")).one()
        assert tuple(old) == ("transactions", None, 2, "output.csv")
        assert connection.execute(text("SELECT issues FROM job_imports WHERE job_id=42")).scalar() == "[]"
        assert connection.execute(text("SELECT count(*) FROM flight_observations")).scalar() == 0
        columns = {column["name"] for column in inspect(connection).get_columns("processing_jobs")}
        assert {"job_kind", "input_sha256"} <= columns
        insert = text("""INSERT INTO flight_observations
            (job_id, tuple_id, row_number, src, flight, sched_dep_time, act_dep_time,
             sched_arr_time, act_arr_time, issues)
            VALUES (:job, :key, :row, 's', 'ZZ-1-AAA-BBB', '', '', '', '', '[]')""")
        connection.execute(insert, {"job": 42, "key": "opaque", "row": 2})
        connection.commit()
        for values in [
            {"job": 42, "key": "opaque", "row": 3},  # Composite observation identity.
            {"job": 42, "key": "different", "row": 2},  # Position within snapshot.
            {"job": 999, "key": "orphan", "row": 2},  # Foreign key.
            {"job": 42, "key": "header", "row": 1},  # Logical data positions.
        ]:
            with pytest.raises(IntegrityError):
                connection.execute(insert, values)
            connection.rollback()
        assert connection.execute(text("SELECT count(*) FROM flight_observations")).scalar() == 1
    isolated.dispose()
