"""Focused HTTP/OpenAPI contracts; dynamic IDs and filenames are not snapshots."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from app.main import app
from app.services.job_processing import process_job
from app.intake.schemas import REQUIRED_COLUMNS
from fastapi.testclient import TestClient
from test_uploads import VALID_CSV


@pytest.mark.parametrize("path,operation_id,success,response_model", [
    ("/api/v1/uploads", "upload_csv_api_v1_uploads_post", "202", "UploadResponse"),
    ("/api/v1/imports/preview", "preview_api_v1_imports_preview_post", "200", None),
])
def test_openapi_multipart_field_contract(path, operation_id, success, response_model):
    schema = app.openapi()
    operation = schema["paths"][path]["post"]
    assert operation["operationId"] == operation_id
    request = operation["requestBody"]
    assert request["required"] is True
    body_ref = request["content"]["multipart/form-data"]["schema"]["$ref"]
    body = schema["components"]["schemas"][body_ref.rsplit("/", 1)[-1]]
    assert body["required"] == ["file"]
    assert set(body["properties"]) == {"file", "import_options"}
    assert body["properties"]["file"]["type"] == "string"
    assert body["properties"]["file"]["contentMediaType"] == "application/octet-stream"
    assert {item["type"] for item in body["properties"]["import_options"]["anyOf"]} == {"string", "null"}
    response = operation["responses"][success]["content"]["application/json"]
    if response_model:
        assert response["schema"] == {"$ref": f"#/components/schemas/{response_model}"}
    assert "422" in operation["responses"]


@pytest.mark.parametrize("path,method,operation_id,request_model,status,response_model", [
    ("/api/v1/imports/templates", "post", "save_template_api_v1_imports_templates_post", "TemplateWrite", "201", None),
    ("/api/v1/imports/templates/{template_id}", "put", "update_template_api_v1_imports_templates__template_id__put", "TemplateWrite", "200", None),
    ("/api/v1/jobs/{job_id}", "get", "get_job_api_v1_jobs__job_id__get", None, "200", "JobDetailResponse"),
    ("/api/v1/jobs/{job_id}/records", "get", "records_api_v1_jobs__job_id__records_get", None, "200", "RecordPage"),
    ("/api/v1/jobs/{job_id}/corrections/validate", "post", "validate_corrections_api_v1_jobs__job_id__corrections_validate_post", "CorrectionRequest", "200", None),
    ("/api/v1/jobs/{job_id}/corrections", "post", "reprocess_api_v1_jobs__job_id__corrections_post", "CorrectionRequest", "202", "UploadResponse"),
])
def test_openapi_named_contracts(path, method, operation_id, request_model, status, response_model):
    operation = app.openapi()["paths"][path][method]
    assert operation["operationId"] == operation_id
    if request_model:
        assert operation["requestBody"]["content"]["application/json"]["schema"] == {
            "$ref": f"#/components/schemas/{request_model}",
        }
    response = operation["responses"][status]["content"]["application/json"]
    if response_model:
        assert response["schema"] == {"$ref": f"#/components/schemas/{response_model}"}
    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HTTPValidationError",
    }


def test_upload_acceptance_and_pending_job_defaults():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/uploads", files={"file": ("contract.csv", VALID_CSV, "text/csv")},
        )
        assert response.status_code == 202
        assert response.headers["content-type"] == "application/json"
        body = response.json()
        assert type(body["job_id"]) is int
        assert body["saved_filename"].endswith(".csv")
        assert Path(body["saved_filename"]).name == body["saved_filename"]
        assert "\\" not in body["saved_filename"]
        assert body == {
            "status": "pending", "error_message": None,
            "message": "Upload accepted for background processing.",
            "original_filename": "contract.csv", "saved_filename": body["saved_filename"],
            "job_id": body["job_id"], "status_url": f"/api/v1/jobs/{body['job_id']}",
        }
        assert response.headers["location"] == body["status_url"]
        detail_response = client.get(body["status_url"])
        assert detail_response.status_code == 200
        detail = detail_response.json()
        datetime.fromisoformat(detail["created_at"])
        assert detail == {
            "id": body["job_id"], "filename_original": "contract.csv",
            "filename_input_saved": body["saved_filename"],
            "filename_cleaned": "", "filename_error_report": "", "status": "pending",
            "total_rows": 0, "valid_rows": 0, "invalid_rows": 0, "error_message": None,
            "created_at": detail["created_at"], "processed_at": None,
            "records_available": False, "parent_job_id": None, "parent_summary": None,
            "child_job_ids": [], "corrections": {}, "attempts": 0,
            "file_size": len(VALID_CSV), "duration_ms": 0, "error_breakdown": {}, "ai_report": None,
            "import_options": {"mapping": {}, "rules": {}, "template_id": None, "template_version": None},
            "analysis": {
                "profiling": {"numeric": {}, "categorical": {}}, "quality": None,
                "anomalies": [], "anomaly_count": 0, "validation_issue_count": 0,
                "duplicate_records": 0, "missing_cells": 0, "error_patterns": [],
                "error_preview": [], "insights": [],
            },
        }


def test_preview_response_and_multipart_mapping_options():
    headers = ["Email Address" if field == "email" else field for field in REQUIRED_COLUMNS]
    mapping = {field: header for field, header in zip(REQUIRED_COLUMNS, headers)}
    source = VALID_CSV.replace(b"customer_id,email,country", b"customer_id,Email Address,country")
    first = {
        "customer_id": "CUST-001", "email": "alice@example.com", "country": "DE",
        "signup_date": "2026-04-01", "order_amount": "125.50", "currency": "EUR",
        "payment_method": "card", "order_status": "completed", "product_category": "electronics",
        "quantity": "2", "discount_percent": "10", "last_login_date": "2026-04-10",
    }
    second = {
        "customer_id": "CUST-002", "email": "bob@example.com", "country": "IN",
        "signup_date": "2026-04-03", "order_amount": "89.99", "currency": "INR",
        "payment_method": "paypal", "order_status": "pending", "product_category": "clothing",
        "quantity": "1", "discount_percent": "5", "last_login_date": "2026-04-09",
    }
    with TestClient(app) as client:
        inspection = client.post(
            "/api/v1/imports/preview", files={"file": ("partner.csv", source, "text/csv")},
        )
        assert inspection.status_code == 200
        assert inspection.json() == {
            "headers": headers, "required_fields": REQUIRED_COLUMNS,
            "suggested_mapping": mapping, "sample_limit": 10,
            "rows": [
                {"row_number": number, "values": {mapping[field]: value for field, value in row.items()}, "issues": []}
                for number, row in ((2, first), (3, second))
            ],
        }
        preview = client.post(
            "/api/v1/imports/preview", files={"file": ("partner.csv", source, "text/csv")},
            data={"import_options": json.dumps({
                "mapping": mapping, "rules": {"order_amount": {"maximum": 100}},
            })},
        )
        assert preview.status_code == 200
        assert preview.json() == {
            "headers": headers, "required_fields": REQUIRED_COLUMNS,
            "suggested_mapping": mapping, "sample_limit": 10,
            "rows": [
                {"row_number": 2, "values": first, "issues": [{
                    "fields": ["order_amount"], "category": "Order Amount",
                    "message": "order_amount exceeds template maximum 100.0",
                }]},
                {"row_number": 3, "values": second, "issues": []},
            ],
        }
        assert client.get("/api/v1/jobs").json()["total"] == 0


@pytest.mark.parametrize("path", ["/api/v1/uploads", "/api/v1/imports/preview"])
def test_multipart_missing_file_and_error_shapes(path):
    with TestClient(app) as client:
        missing = client.post(path, data={"import_options": "{}"})
        assert missing.status_code == 422
        errors = missing.json()["detail"]
        assert len(errors) == 1
        assert errors[0]["type"] == "missing"
        assert errors[0]["loc"] == ["body", "file"]
        assert isinstance(errors[0]["msg"], str) and errors[0]["msg"]
        unknown = client.post(
            path, files={"file": ("contract.csv", VALID_CSV, "text/csv")},
            data={"import_options": json.dumps({"unexpected": True})},
        )
        assert unknown.status_code == 422
        assert isinstance(unknown.json()["detail"], str) and unknown.json()["detail"]
        malformed = client.post(
            path, files={"file": ("contract.csv", VALID_CSV, "text/csv")},
            data={"import_options": '{"mapping":'},
        )
        assert malformed.status_code == 422
        assert isinstance(malformed.json()["detail"], str)
        assert malformed.json()["detail"]
        assert "location" not in malformed.headers
        assert client.get("/api/v1/jobs").json()["total"] == 0


def test_template_creation_defaults_and_trimmed_name():
    options = {"mapping": {field: field for field in REQUIRED_COLUMNS}}
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/templates", json={"name": " Partner ", "options": options},
        )
        assert response.status_code == 201
        template = response.json()
        assert template == {
            "id": template["id"], "name": "Partner", "version": 1,
            "updated_at": template["updated_at"],
            "options": {**options, "rules": {}, "template_id": None, "template_version": None},
        }


def test_correction_validation_and_child_acceptance_contract():
    source = VALID_CSV.replace(b"alice@example.com", b"bad-email")
    with TestClient(app) as client:
        uploaded = client.post(
            "/api/v1/uploads", files={"file": ("parent.csv", source, "text/csv")},
        )
        parent = uploaded.json()["job_id"]
        assert process_job(parent) == "completed"
        url = f"/api/v1/jobs/{parent}"
        original = client.get(url + "/records").json()["records"][0]["values"]
        patches = {"patches": {"2": {"email": "fixed@example.com"}}}
        invalid = client.post(url + "/corrections", json={**patches, "unexpected": True})
        assert invalid.status_code == 422
        assert invalid.json()["detail"][0]["type"] == "extra_forbidden"
        assert invalid.json()["detail"][0]["loc"] == ["body", "unexpected"]
        validation = client.post(url + "/corrections/validate", json=patches)
        assert validation.status_code == 200
        checked = validation.json()
        assert set(checked) == {"rows", "valid", "message"}
        assert checked["rows"] == [{
            "row_number": 2, "values": {**original, "email": "fixed@example.com"}, "issues": [],
        }]
        assert checked["valid"] is True
        assert isinstance(checked["message"], str) and checked["message"]
        response = client.post(url + "/corrections", json=patches)
        assert response.status_code == 202
        child = response.json()
        assert child == {
            "status": "pending", "error_message": None,
            "message": "Upload accepted for background processing.",
            "original_filename": "parent.csv", "saved_filename": child["saved_filename"],
            "job_id": child["job_id"], "status_url": f"/api/v1/jobs/{child['job_id']}",
        }
        assert child["saved_filename"] != uploaded.json()["saved_filename"]
        assert child["saved_filename"].endswith(".csv")
        assert Path(child["saved_filename"]).name == child["saved_filename"]
        assert "\\" not in child["saved_filename"]
        assert response.headers["location"] == child["status_url"]
        pending = client.get(child["status_url"]).json()
        assert pending["parent_job_id"] == parent
        assert pending["corrections"] == {"2": {"email": {"before": "bad-email", "after": "fixed@example.com"}}}
        assert client.get(child["status_url"] + "/download/input").content == source
