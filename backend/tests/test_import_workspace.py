import csv
import io
import json

from app.core.config import INPUT_DIR
from app.core.db import engine
from app.main import app
from app.models.processing_job import JobImport, JobRecord
from app.services.job_processing import process_job
from app.intake.schemas import REQUIRED_COLUMNS
from app.services.validator import validate_row
from fastapi.testclient import TestClient
from sqlmodel import Session, select

HEADER = ",".join(REQUIRED_COLUMNS)
GOOD = (
    "C1,alice@example.com,DE,2026-04-01,125.50,EUR,card,completed,books,2,10,2026-04-10"
)
BAD = GOOD.replace("alice@example.com", "bad-email")
IDENTITY = {field: field for field in REQUIRED_COLUMNS}


def upload(client, content, options=None):
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("workspace.csv", content.encode(), "text/csv")},
        data={"import_options": json.dumps(options)} if options else {},
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    process_job(job_id)
    return job_id


def test_explorer_searches_beyond_preview_and_exports_same_filter():
    rows = [
        GOOD.replace("C1,", f"C{i},").replace("alice@example.com", f"bad-{i}")
        for i in range(130)
    ]
    with TestClient(app) as client:
        job = upload(client, "\n".join([HEADER, *rows]))
        response = client.get(
            f"/api/v1/jobs/{job}/records?page=6&page_size=25&status=rejected"
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 130
        assert len(response.json()["records"]) == 5
        filtered = (
            f"/api/v1/jobs/{job}/records?search=bad-129&category=Email&status=rejected"
        )
        row = client.get(filtered).json()["records"][0]
        assert row["row_number"] == 131 and row["issues"][0]["fields"] == ["email"]
        exported = client.get(filtered.replace("/records?", "/records/export?"))
        parsed = list(csv.DictReader(io.StringIO(exported.text)))
        assert len(parsed) == 1 and parsed[0]["row_number"] == "131"
        assert client.get(f"/api/v1/jobs/{job}/records?search=%25").json()["total"] == 0
        assert (
            client.get(
                f"/api/v1/jobs/{job}/records?sort=email&direction=desc"
            ).status_code
            == 200
        )
        assert client.get(f"/api/v1/jobs/{job}/records?sort=DROP").status_code == 422
        assert (
            client.get(f"/api/v1/jobs/{job}/records?page_size=101").status_code == 422
        )
        assert process_job(job) == "ignored"
        with Session(engine) as session:
            assert (
                len(
                    session.exec(select(JobRecord).where(JobRecord.job_id == job)).all()
                )
                == 130
            )


def test_corrections_preserve_original_and_publish_linked_comparison():
    with TestClient(app) as client:
        parent = upload(client, "\n".join([HEADER, GOOD, BAD.replace("C1,", "C2,")]))
        original = client.get(f"/api/v1/jobs/{parent}/download/input").content
        parent_score = client.get(f"/api/v1/jobs/{parent}").json()["analysis"][
            "quality"
        ]["score"]
        body = {"patches": {"3": {"email": "bob@example.com"}}}
        preview = client.post(f"/api/v1/jobs/{parent}/corrections/validate", json=body)
        assert preview.json()["valid"] is True
        response = client.post(f"/api/v1/jobs/{parent}/corrections", json=body)
        assert response.status_code == 202, response.text
        child = response.json()["job_id"]
        assert process_job(child) == "completed"
        result = client.get(f"/api/v1/jobs/{child}").json()
        assert result["valid_rows"] == 2 and result["invalid_rows"] == 0
        assert result["parent_job_id"] == parent
        assert result["parent_summary"]["score"] == parent_score
        assert result["corrections"]["3"]["email"] == {
            "before": "bad-email",
            "after": "bob@example.com",
        }
        assert child in client.get(f"/api/v1/jobs/{parent}").json()["child_job_ids"]
        assert client.get(f"/api/v1/jobs/{parent}/download/input").content == original
        assert client.get(f"/api/v1/jobs/{parent}").json()["invalid_rows"] == 1
        assert (
            "bob@example.com" in client.get(f"/api/v1/jobs/{child}/download/clean").text
        )
        # Repeated submissions branch from the same immutable parent.
        branch = client.post(f"/api/v1/jobs/{parent}/corrections", json=body).json()[
            "job_id"
        ]
        assert branch != child


def test_corrections_recheck_duplicates_and_carry_forward_edits():
    with TestClient(app) as client:
        parent = upload(client, "\n".join([HEADER, GOOD, BAD]))
        fix = {"patches": {"3": {"email": "alice@example.com"}}}
        assert client.post(
            f"/api/v1/jobs/{parent}/corrections/validate", json=fix
        ).json()["valid"]
        child = client.post(f"/api/v1/jobs/{parent}/corrections", json=fix).json()[
            "job_id"
        ]
        process_job(child)
        detail = client.get(f"/api/v1/jobs/{child}").json()
        assert (
            detail["invalid_rows"] == 1 and detail["analysis"]["duplicate_records"] == 1
        )
        fix_duplicate = {"patches": {"3": {"customer_id": "C2"}}}
        grandchild = client.post(
            f"/api/v1/jobs/{child}/corrections", json=fix_duplicate
        ).json()["job_id"]
        process_job(grandchild)
        assert client.get(f"/api/v1/jobs/{grandchild}").json()["valid_rows"] == 2
        rows = client.get(f"/api/v1/jobs/{grandchild}/records").json()["records"]
        assert rows[1]["values"]["email"] == "alice@example.com"
        assert rows[1]["values"]["customer_id"] == "C2"


def test_correction_guards_and_no_draft_mutation():
    with TestClient(app) as client:
        parent = upload(client, "\n".join([HEADER, GOOD, BAD]))
        for patches in (
            {"2": {"email": "new@example.com"}},
            {"100": {"email": "x@example.com"}},
            {"3": {"unknown": "x"}},
            {"3": {"email": "bad-email"}},
        ):
            assert (
                client.post(
                    f"/api/v1/jobs/{parent}/corrections", json={"patches": patches}
                ).status_code
                == 422
            )
        bad = {"patches": {"3": {"email": "still-invalid"}}}
        assert (
            client.post(f"/api/v1/jobs/{parent}/corrections/validate", json=bad).json()[
                "valid"
            ]
            is False
        )
        assert (
            client.post(f"/api/v1/jobs/{parent}/corrections", json=bad).status_code
            == 422
        )
        assert client.get("/api/v1/jobs").json()["total"] == 1
        row = client.get(f"/api/v1/jobs/{parent}/records?status=rejected").json()[
            "records"
        ][0]
        assert row["values"]["email"] == "bad-email"
        malformed = upload(client, HEADER + "\n" + BAD + ",extra")
        assert (
            client.post(
                f"/api/v1/jobs/{malformed}/corrections",
                json={"patches": {"2": {"email": "ok@example.com"}}},
            ).status_code
            == 422
        )


def test_mapping_preview_templates_and_snapshot_versions():
    source_headers = [field.replace("_", " ").title() for field in REQUIRED_COLUMNS]
    mapping = dict(zip(REQUIRED_COLUMNS, source_headers))
    content = ",".join(source_headers) + "\n" + GOOD
    options = {"mapping": mapping, "rules": {"order_amount": {"maximum": 100}}}
    with TestClient(app) as client:
        before = set(INPUT_DIR.glob("*"))
        preview = client.post(
            "/api/v1/imports/preview",
            files={"file": ("mapped.csv", content, "text/csv")},
        )
        assert preview.status_code == 200
        assert preview.json()["suggested_mapping"] == mapping
        assert set(INPUT_DIR.glob("*")) == before
        assert client.get("/api/v1/jobs").json()["total"] == 0
        checked = client.post(
            "/api/v1/imports/preview",
            files={"file": ("mapped.csv", content, "text/csv")},
            data={"import_options": json.dumps(options)},
        )
        assert "maximum" in checked.json()["rows"][0]["issues"][0]["message"]
        template = client.post(
            "/api/v1/imports/templates",
            json={"name": "Partner transactions", "options": options},
        ).json()
        chosen = {**options, "template_id": template["id"], "template_version": 1}
        job = upload(client, content, chosen)
        assert client.get(f"/api/v1/jobs/{job}").json()["invalid_rows"] == 1
        updated = client.put(
            f"/api/v1/imports/templates/{template['id']}",
            json={
                "name": "Partner transactions",
                "options": {"mapping": mapping, "rules": {}},
                "expected_version": 1,
            },
        )
        assert updated.status_code == 200 and updated.json()["version"] == 2
        assert (
            client.put(
                f"/api/v1/imports/templates/{template['id']}",
                json={"name": "stale", "options": options, "expected_version": 1},
            ).status_code
            == 409
        )
        assert (
            client.get(f"/api/v1/jobs/{job}").json()["import_options"]["rules"][
                "order_amount"
            ]["maximum"]
            == 100
        )
        stale = client.post(
            "/api/v1/uploads",
            files={"file": ("mapped.csv", content, "text/csv")},
            data={"import_options": json.dumps(chosen)},
        )
        assert stale.status_code == 409
        assert stale.json() == {
            "detail": "Template changed or no longer exists. Reload templates and preview again.",
        }
        assert client.get("/api/v1/jobs").json()["total"] == 1
        assert len(client.get("/api/v1/imports/templates").json()) == 1
        # Even after a template update, corrections reuse the job's saved rules.
        body = {"patches": {"2": {"order_amount": "90"}}}
        child = client.post(f"/api/v1/jobs/{job}/corrections", json=body).json()[
            "job_id"
        ]
        process_job(child)
        assert client.get(f"/api/v1/jobs/{child}").json()["valid_rows"] == 1
        assert (
            client.get(f"/api/v1/jobs/{child}").json()["import_options"][
                "template_version"
            ]
            == 1
        )


def test_date_and_allowed_value_rules_normalize_without_changing_source():
    disallowed = GOOD.replace("C1,", "C2,").replace(",DE,", ",US,")
    assert validate_row(dict(zip(REQUIRED_COLUMNS, disallowed.split(","))), 3) == []
    text = (
        HEADER
        + "\n"
        + GOOD.replace("2026-04-01", "01/04/2026").replace("2026-04-10", "10/04/2026")
        + "\n"
        + disallowed.replace("2026-04-01", "01/04/2026").replace("2026-04-10", "10/04/2026")
    )
    options = {
        "mapping": IDENTITY,
        "rules": {
            "signup_date": {"date_format": "%d/%m/%Y"},
            "last_login_date": {"date_format": "%d/%m/%Y"},
            "country": {"allowed_values": ["DE"]},
        },
    }
    with TestClient(app) as client:
        job = upload(client, text, options)
        detail = client.get(f"/api/v1/jobs/{job}").json()
        assert (detail["valid_rows"], detail["invalid_rows"]) == (1, 1)
        assert "2026-04-01" in client.get(f"/api/v1/jobs/{job}/download/clean").text
        row = client.get(f"/api/v1/jobs/{job}/records").json()["records"][0]
        assert row["values"]["signup_date"] == "01/04/2026"
        assert row["normalized"]["signup_date"] == "2026-04-01"
        rejected = client.get(f"/api/v1/jobs/{job}/records?status=rejected").json()["records"]
        assert len(rejected) == 1
        assert rejected[0]["values"]["country"] == "US"
        assert rejected[0]["normalized"] == {}
        assert rejected[0]["issues"] == [{
            "fields": ["country"], "category": "Country / Currency",
            "message": "country is outside template allowed values",
        }]


def test_import_configuration_rejects_unsafe_or_ambiguous_options():
    with TestClient(app) as client:
        invalid = [
            {"mapping": {"email": "Email"}},
            {"mapping": {k: "same" for k in REQUIRED_COLUMNS}},
            {"mapping": IDENTITY, "rules": {"unknown": {"required": True}}},
            {"mapping": IDENTITY, "rules": {"email": {"minimum": 0}}},
            {
                "mapping": IDENTITY,
                "rules": {"order_amount": {"minimum": 10, "maximum": 1}},
            },
            {
                "mapping": IDENTITY,
                "rules": {"signup_date": {"date_format": "arbitrary"}},
            },
        ]
        for options in invalid:
            assert (
                client.post(
                    "/api/v1/uploads",
                    files={"file": ("test.csv", HEADER + "\n" + GOOD, "text/csv")},
                    data={"import_options": json.dumps(options)},
                ).status_code
                == 422
            )
        assert (
            client.post(
                "/api/v1/imports/preview",
                files={"file": ("duplicate.csv", "email,email\na,b", "text/csv")},
            ).status_code
            == 422
        )
        assert client.get("/api/v1/jobs").json()["total"] == 0
        missing_source = {**IDENTITY, "email": "not present"}
        assert (
            client.post(
                "/api/v1/uploads",
                files={"file": ("test.csv", HEADER + "\n" + GOOD, "text/csv")},
                data={"import_options": json.dumps({"mapping": missing_source})},
            ).status_code
            == 422
        )


def test_old_jobs_remain_readable_without_false_record_availability():
    with TestClient(app) as client:
        job = upload(client, HEADER + "\n" + GOOD)
        with Session(engine) as session:
            session.delete(session.get(JobImport, job))
            session.commit()
        assert client.get(f"/api/v1/jobs/{job}").json()["records_available"] is False
        assert client.get(f"/api/v1/jobs/{job}/records").status_code == 409
        assert client.get(f"/api/v1/jobs/{job}/download/clean").status_code == 200


def test_record_publication_rolls_back_with_failed_result_commit(monkeypatch):
    from datetime import datetime, timedelta

    import pytest
    from app.models.processing_job import JobExecution
    from app.services.dispatch import recover_expired
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.sql.dml import Insert

    execute = Session.execute

    def unavailable(self, statement, *args, **kwargs):
        if isinstance(statement, Insert) and statement.table.name == "job_records":
            raise OperationalError("insert", {}, Exception("database unavailable"))
        return execute(self, statement, *args, **kwargs)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("atomic.csv", HEADER + "\n" + GOOD, "text/csv")},
        )
        job = response.json()["job_id"]
        monkeypatch.setattr(Session, "execute", unavailable)
        with pytest.raises(OperationalError):
            process_job(job)
        monkeypatch.setattr(Session, "execute", execute)
        assert client.get(f"/api/v1/jobs/{job}").json()["status"] == "processing"
        with Session(engine) as session:
            assert (
                session.exec(select(JobRecord).where(JobRecord.job_id == job)).all()
                == []
            )
            lease = session.get(JobExecution, job)
            lease.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
            session.add(lease)
            session.commit()
        recover_expired(datetime.utcnow())
        assert process_job(job) == "completed"
        assert client.get(f"/api/v1/jobs/{job}/records").json()["total"] == 1
