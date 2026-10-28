"""A fixed mapped dataset protects processing, artifacts and persisted analytics."""

import csv
import io
import json

from app.core.db import engine
from app.main import app
from app.models.processing_job import JobAnalysis, JobRecord, ProcessingJob
from app.services.job_processing import process_job
from fastapi.testclient import TestClient
from sqlmodel import Session, select


def test_mapped_csv_records_reports_and_persisted_analytics():
    fields = (
        "customer_id,email,country,signup_date,order_amount,currency,payment_method,"
        "order_status,product_category,quantity,discount_percent,last_login_date"
    ).split(",")
    headers = [field.replace("_", " ").title() for field in fields]
    good = dict(zip(fields, [
        " c-1 ", " ALICE@EXAMPLE.COM ", " de ", "01/04/2026", "12.5", " eur ",
        " CARD ", " COMPLETED ", ' Books,\n"Home" ', "02", "5", "10/04/2026",
    ]))
    bad = dict(zip(fields, [
        " c-2 ", "bad-email", "DE", "01/04/2026", "-5", "EUR", "card",
        "completed", "Needs, review", "0", "150", "10/04/2026",
    ]))
    unusual = dict(zip(fields, [
        "c-3", "carol@example.com", "DE", "01/04/2026", "1500", "EUR", "card",
        "completed", "books", "21", "60", "10/04/2026",
    ]))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in (good, bad, unusual, good):
        writer.writerow([row[field] for field in fields])
    payload = buffer.getvalue().encode("utf-8")
    options = {
        "mapping": dict(zip(fields, headers)),
        "rules": {field: {"date_format": "%d/%m/%Y"} for field in ("signup_date", "last_login_date")},
    }
    normalized_good = {
        "customer_id": "C-1", "email": "alice@example.com", "country": "DE",
        "signup_date": "2026-04-01", "order_amount": "12.50", "currency": "EUR",
        "payment_method": "card", "order_status": "completed",
        "product_category": 'Books,\n"Home"', "quantity": "2", "discount_percent": "5.00",
        "last_login_date": "2026-04-10",
    }
    normalized_unusual = {
        **unusual, "customer_id": "C-3", "signup_date": "2026-04-01",
        "last_login_date": "2026-04-10", "order_amount": "1500.00", "discount_percent": "60.00",
    }
    messages = ["email must be valid", "negative order_amount", "quantity must be > 0", "invalid discount_percent"]
    issues = [
        {"fields": [field], "category": category, "message": message}
        for field, category, message in zip(
            ("email", "order_amount", "quantity", "discount_percent"),
            ("Email", "Order Amount", "Quantity", "Discount"), messages,
        )
    ]
    duplicate = "duplicate record: identical required field values"
    error_rows = [
        {"row_number": "3", **bad, "errors": "; ".join(messages)},
        {"row_number": "5", **good, "errors": duplicate},
    ]
    expected_records = [
        {"row_number": 2, "status": "accepted", "values": good, "normalized": normalized_good, "issues": []},
        {"row_number": 3, "status": "rejected", "values": bad, "normalized": {}, "issues": issues},
        {"row_number": 4, "status": "accepted", "values": unusual, "normalized": normalized_unusual, "issues": []},
        {"row_number": 5, "status": "rejected", "values": good, "normalized": {},
         "issues": [{"fields": [], "category": "Duplicate Record", "message": duplicate}]},
    ]
    expected_analysis = {
        "profiling": {
            "numeric": {
                "order_amount": {"count": 2, "min": 12.5, "max": 1500.0, "average": 756.25},
                "quantity": {"count": 2, "min": 2.0, "max": 21.0, "average": 11.5},
                "discount_percent": {"count": 2, "min": 5.0, "max": 60.0, "average": 32.5},
            },
            "categorical": {
                "country": [{"value": "DE", "count": 2}],
                "currency": [{"value": "EUR", "count": 2}],
                "payment_method": [{"value": "card", "count": 2}],
                "order_status": [{"value": "completed", "count": 2}],
                "product_category": [{"value": 'Books,\n"Home"', "count": 1}, {"value": "books", "count": 1}],
            },
        },
        "quality": {"score": 62.5, "dimensions": {
            "validity": 50.0, "completeness": 100.0, "uniqueness": 75.0, "anomaly_health": 50.0,
        }},
        "anomalies": [
            {"row": 4, "column": "order_amount", "value": 1500.0, "message": "High-value order detected."},
            {"row": 4, "column": "quantity", "value": 21.0, "message": "Unusually large quantity detected."},
            {"row": 4, "column": "discount_percent", "value": 60.0, "message": "High discount detected."},
        ],
        "anomaly_count": 3, "validation_issue_count": 5, "duplicate_records": 1, "missing_cells": 0,
        "error_patterns": [
            {"pattern": "email must be valid + invalid discount_percent + negative order_amount + quantity must be > 0", "count": 1},
            {"pattern": duplicate, "count": 1},
        ],
        "error_preview": error_rows,
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/uploads", files={"file": ("mapped.csv", payload, "text/csv")},
            data={"import_options": json.dumps(options)},
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert process_job(job_id) == "completed"
        url = f"/api/v1/jobs/{job_id}"
        response = client.get(url)
        assert response.status_code == 200
        detail = response.json()
        assert detail["id"] == job_id
        assert detail["status"] == "completed"
        assert detail["filename_original"] == "mapped.csv"
        assert detail["file_size"] == len(payload)
        assert detail["duration_ms"] >= 0
        assert detail["filename_cleaned"].endswith("_clean.csv")
        assert detail["filename_error_report"].endswith("_errors.csv")
        assert (detail["total_rows"], detail["valid_rows"], detail["invalid_rows"]) == (4, 2, 2)
        assert detail["records_available"] is True
        analysis = detail["analysis"]
        assert isinstance(analysis["insights"], list) and analysis["insights"]
        assert all(isinstance(text, str) and text.strip() for text in analysis["insights"])
        assert {key: value for key, value in analysis.items() if key != "insights"} == expected_analysis
        assert detail["error_breakdown"] == {"Email": 1, "Order Amount": 1, "Quantity": 1, "Discount": 1, "Duplicate Record": 1}
        assert client.get(url + "/records").json() == {
            "records": expected_records, "total": 4, "page": 1, "page_size": 25, "fields": fields,
        }
        assert client.get(url + "/download/input").content == payload
        clean = client.get(url + "/download/clean")
        assert clean.status_code == 200
        assert clean.headers["content-type"].startswith("text/csv")
        assert clean.headers["content-disposition"] == f'attachment; filename="{detail["filename_cleaned"]}"'
        assert clean.content == (
            ",".join(fields) + "\r\n"
            'C-1,alice@example.com,DE,2026-04-01,12.50,EUR,card,completed,"Books,\n""Home""",2,5.00,2026-04-10\r\n'
            'C-3,carol@example.com,DE,2026-04-01,1500.00,EUR,card,completed,books,21,60.00,2026-04-10\r\n'
        ).encode("utf-8")
        errors = client.get(url + "/download/errors")
        assert errors.status_code == 200
        assert errors.headers["content-type"].startswith("text/csv")
        assert errors.headers["content-disposition"] == f'attachment; filename="{detail["filename_error_report"]}"'
        parsed = csv.DictReader(io.StringIO(errors.text, newline=""))
        assert parsed.fieldnames == ["row_number", *fields, "errors"]
        assert list(parsed) == error_rows
        assert errors.content.count(b"\r\n") == 3
        assert b'"Needs, review"' in errors.content
        assert b'" Books,\n""Home"" "' in errors.content

    with Session(engine) as session:
        stored_job = session.get(ProcessingJob, job_id)
        assert stored_job.status == "completed"
        assert (stored_job.total_rows, stored_job.valid_rows, stored_job.invalid_rows) == (4, 2, 2)
        assert session.get(JobAnalysis, job_id).analysis == analysis
        stored_records = session.exec(
            select(JobRecord).where(JobRecord.job_id == job_id).order_by(JobRecord.row_number)
        ).all()
        assert [record.model_dump(include={"row_number", "status", "values", "normalized", "issues"})
                for record in stored_records] == expected_records
