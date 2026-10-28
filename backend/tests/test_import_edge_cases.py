"""Boundary and failure-path coverage for mapped imports and correction APIs."""

import csv
import io
import json

import pytest
from app.core.config import INPUT_DIR
from app.main import app
from app.services.job_processing import process_job
from app.services.validator import REQUIRED_COLUMNS
from fastapi.testclient import TestClient

HEADER = ",".join(REQUIRED_COLUMNS)
ROW = "C1,bad-email,DE,2026-04-01,125.50,EUR,card,completed,books,2,10,2026-04-10"
OPTIONS = {"mapping": dict(zip(REQUIRED_COLUMNS, REQUIRED_COLUMNS))}


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def completed(client):
    response = client.post(
        "/api/v1/uploads", files={"file": ("test.csv", HEADER + "\n" + ROW, "text/csv")}
    )
    assert response.status_code == 202
    job = response.json()["job_id"]
    assert process_job(job) == "completed"
    return job


@pytest.mark.parametrize(
    "content", [b"", b"email,email\na,b", b"email\n\xff", b'email\n"unterminated']
)
def test_malformed_preview_cleans_up_without_creating_job(client, content):
    before = set(INPUT_DIR.glob("*"))
    response = client.post(
        "/api/v1/imports/preview", files={"file": ("bad.csv", content, "text/csv")}
    )
    assert response.status_code == 422
    assert set(INPUT_DIR.glob("*")) == before
    assert client.get("/api/v1/jobs").json()["total"] == 0


def test_bom_crlf_and_multiline_quotes_preserve_records_and_exports(client):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(REQUIRED_COLUMNS)
    values = ROW.replace("bad-email", "alice@example.com").split(",")
    values[0] = 'customer, with comma\nand "quotes"'
    writer.writerow(values)
    payload = b"\xef\xbb\xbf" + buffer.getvalue().encode()
    response = client.post(
        "/api/v1/uploads", files={"file": ("quoted.csv", payload, "text/csv")}
    )
    assert response.status_code == 202
    job = response.json()["job_id"]
    assert process_job(job) == "completed"
    assert client.get(f"/api/v1/jobs/{job}").json()["valid_rows"] == 1
    record = client.get(f"/api/v1/jobs/{job}/records").json()["records"][0]
    assert record["status"] == "accepted"
    assert record["values"]["customer_id"] == values[0]
    exported = client.get(f"/api/v1/jobs/{job}/records/export")
    assert (
        list(csv.DictReader(io.StringIO(exported.text)))[0]["customer_id"] == values[0]
    )
    assert client.get(f"/api/v1/jobs/{job}/download/input").content == payload


@pytest.mark.parametrize(
    "patches",
    [
        {},
        {"1": {"email": "a@example.com"}},
        {"2147483648": {"email": "a@example.com"}},
        {"2": {}},
        {"2": {"email": "x" * 10001}},
        {str(i): {"email": "a@example.com"} for i in range(2, 203)},
        {str(i): {"customer_id": "é" * 10000} for i in range(2, 55)},
    ],
)
def test_invalid_correction_boundaries_have_no_side_effects(client, patches):
    job = completed(client)
    before = set(INPUT_DIR.glob("*"))
    for suffix in ("corrections/validate", "corrections"):
        response = client.post(
            f"/api/v1/jobs/{job}/{suffix}", json={"patches": patches}
        )
        assert response.status_code == 422, response.text
    assert client.get("/api/v1/jobs").json()["total"] == 1
    assert set(INPUT_DIR.glob("*")) == before
    assert (
        client.get(f"/api/v1/jobs/{job}/records").json()["records"][0]["values"][
            "email"
        ]
        == "bad-email"
    )


def test_missing_original_blocks_reprocessing_without_child(client):
    job = completed(client)
    detail = client.get(f"/api/v1/jobs/{job}").json()
    # Resolve the stored path through metadata, not a public download filename.
    from app.core.db import engine
    from app.models.processing_job import ProcessingJob
    from sqlmodel import Session

    with Session(engine) as session:
        path = INPUT_DIR / session.get(ProcessingJob, job).filename_input_saved
    path.unlink()
    response = client.post(
        f"/api/v1/jobs/{job}/corrections",
        json={"patches": {"2": {"email": "fixed@example.com"}}},
    )
    assert response.status_code == 404
    assert client.get("/api/v1/jobs").json()["total"] == 1
    assert (
        client.get(f"/api/v1/jobs/{job}").json()["invalid_rows"]
        == detail["invalid_rows"]
    )


def test_empty_filter_export_retains_headers_and_out_of_range_page_is_empty(client):
    job = completed(client)
    base = f"/api/v1/jobs/{job}/records"
    response = client.get(base, params={"page": 999})
    assert response.status_code == 200
    assert response.json()["records"] == [] and response.json()["total"] == 1
    exported = client.get(base + "/export", params={"search": "not-present"})
    assert exported.status_code == 200
    parsed = csv.DictReader(io.StringIO(exported.text))
    assert parsed.fieldnames == ["row_number", "status", *REQUIRED_COLUMNS, "errors"]
    assert list(parsed) == []


def test_template_settings_cannot_be_spoofed_or_updated_without_version(client):
    template = client.post(
        "/api/v1/imports/templates", json={"name": "Partner", "options": OPTIONS}
    ).json()
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("test.csv", HEADER + "\n" + ROW, "text/csv")},
        data={
            "import_options": json.dumps(
                {
                    **OPTIONS,
                    "template_id": template["id"],
                    "template_version": 1,
                    "rules": {"order_amount": {"maximum": 1}},
                }
            )
        },
    )
    assert response.status_code == 422
    assert client.get("/api/v1/jobs").json()["total"] == 0
    response = client.put(
        f"/api/v1/imports/templates/{template['id']}",
        json={"name": "Overwrite", "options": OPTIONS},
    )
    assert response.status_code == 422
    stored = client.get("/api/v1/imports/templates").json()[0]
    assert stored["name"] == "Partner" and stored["version"] == 1


def test_upload_size_limit_accepts_boundary_and_cleans_up_overflow(client, monkeypatch):
    from app.utils import file_io

    payload = (HEADER + "\n" + ROW).encode()
    monkeypatch.setattr(file_io, "MAX_UPLOAD_BYTES", len(payload))
    before = set(INPUT_DIR.glob("*"))
    response = client.post(
        "/api/v1/imports/preview", files={"file": ("exact.csv", payload, "text/csv")}
    )
    assert response.status_code == 200
    response = client.post(
        "/api/v1/imports/preview",
        files={"file": ("large.csv", payload + b"\n", "text/csv")},
    )
    assert response.status_code == 413
    assert set(INPUT_DIR.glob("*")) == before
    assert client.get("/api/v1/jobs").json()["total"] == 0


def test_preview_sample_does_not_hide_later_worker_validation_errors(client):
    good = ROW.replace("bad-email", "alice@example.com")
    content = "\n".join(
        [HEADER, *[good.replace("C1,", f"C{i},") for i in range(10)], ROW]
    )
    preview = client.post(
        "/api/v1/imports/preview",
        files={"file": ("sample.csv", content, "text/csv")},
        data={"import_options": json.dumps(OPTIONS)},
    )
    assert preview.status_code == 200
    assert len(preview.json()["rows"]) == 10
    assert all(not row["issues"] for row in preview.json()["rows"])
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("sample.csv", content, "text/csv")},
        data={"import_options": json.dumps(OPTIONS)},
    )
    assert response.status_code == 202
    job = response.json()["job_id"]
    assert process_job(job) == "completed"
    detail = client.get(f"/api/v1/jobs/{job}").json()
    assert (detail["valid_rows"], detail["invalid_rows"]) == (10, 1)
    assert (
        client.get(f"/api/v1/jobs/{job}/records?status=rejected").json()["records"][0][
            "row_number"
        ]
        == 12
    )
