import json
from types import SimpleNamespace

import pytest
from app.core.config import INPUT_DIR
from app.main import app
from app.analytics.schemas import AIReport
from app.analytics.analysis import calculate_quality
from app.intake.schemas import REQUIRED_COLUMNS
from app.intake.validation import validate_row
from app.tasks import process_job_task
from fastapi.testclient import TestClient
from pydantic import ValidationError

HEADER = ",".join(REQUIRED_COLUMNS)
ROW = "C1,alice@example.com,DE,2026-04-01,125.50,EUR,card,completed,electronics,2,10,2026-04-10"


def upload(client, text, name="sample.csv"):
    response = client.post(
        "/api/v1/uploads", files={"file": (name, text.encode(), "text/csv")}
    )
    assert response.status_code == 202
    result = response.json()
    assert result["status"] == "pending"
    process_job_task.apply(args=[result["job_id"]], throw=True)
    detail = client.get(result["status_url"]).json()
    return {**result, **detail}


def test_header_failure_persisted_and_safe_download():
    with TestClient(app) as client:
        result = upload(client, "email\nalice@example.com\n")
        assert result["status"] == "failed"
        detail = client.get(f"/api/v1/jobs/{result['job_id']}").json()
        assert detail["status"] == "failed"
        assert "Missing required columns" in detail["error_message"]
        assert (
            client.get(f"/api/v1/jobs/{result['job_id']}/download/clean").status_code
            == 404
        )
        assert (
            client.get(f"/api/v1/jobs/{result['job_id']}/download/errors").status_code
            == 200
        )
        assert (
            client.post(f"/api/v1/jobs/{result['job_id']}/ai-analysis").status_code
            == 409
        )
        assert "saved_path" not in result
        assert "cleaned_path" not in result


def test_pagination_search_and_status():
    with TestClient(app) as client:
        upload(client, HEADER + "\n" + ROW, "alpha.csv")
        upload(client, HEADER + "\n" + ROW, "beta.csv")
        upload(client, "bad\nvalue", "broken.csv")
        assert client.get("/api/v1/jobs?page=1&page_size=1").json()["total"] == 3
        assert len(client.get("/api/v1/jobs?page=2&page_size=1").json()["jobs"]) == 1
        assert client.get("/api/v1/jobs?status=failed").json()["total"] == 1
        assert client.get("/api/v1/jobs?search=alpha").json()["total"] == 1
        assert client.get("/api/v1/jobs?search=%25").json()["total"] == 0
        assert client.get("/api/v1/jobs?page=0").status_code == 422


def test_file_names_and_repeated_uploads():
    with TestClient(app) as client:
        first = upload(client, HEADER + "\n" + ROW, "../../report.csv")
        second = upload(client, HEADER + "\n" + ROW, "../../report.csv")
        assert "/" not in first["saved_filename"]
        assert (INPUT_DIR / first["saved_filename"]).is_file()
        assert first["filename_cleaned"] != second["filename_cleaned"]


def test_size_limit_and_partial_cleanup(monkeypatch):
    monkeypatch.setattr("app.utils.file_io.MAX_UPLOAD_BYTES", 4)
    before = set(INPUT_DIR.glob("*"))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/uploads", files={"file": ("large.csv", b"12345", "text/csv")}
        )
        assert response.status_code == 413
        assert client.get("/api/v1/jobs").json()["total"] == 0
    assert set(INPUT_DIR.glob("*")) == before


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("order_amount", "NaN", "invalid order_amount"),
        ("order_amount", "Infinity", "invalid order_amount"),
        ("discount_percent", "NaN", "invalid discount_percent"),
        ("email", "two@@example.com", "email must be valid"),
        ("last_login_date", "2026-03-01", "last_login_date precedes signup_date"),
    ],
)
def test_stronger_validation(field, value, expected):
    row = dict(zip(REQUIRED_COLUMNS, ROW.split(",")))
    row[field] = value
    assert expected in validate_row(row, 2)


def test_quality_score_examples_and_empty_dataset():
    assert calculate_quality(0, 0, 0, 12, 0, 0)["score"] is None
    assert calculate_quality(10, 10, 0, 12, 0, 0)["score"] == 100
    assert calculate_quality(10, 8, 12, 12, 1, 2)["score"] == 82.5


@pytest.mark.parametrize("score,error_type", [
    (-1.0, "greater_than_equal"), (101.0, "less_than_equal"),
])
def test_ai_report_rejects_only_out_of_range_quality_score(score, error_type):
    report = {
        "quality_score": score, "severity": "low", "executive_summary": "Good quality.",
        "key_issues": [], "recommended_actions": [], "business_impact": "Ready for review.",
    }
    with pytest.raises(ValidationError) as error:
        AIReport.model_validate(report)
    assert [(item["loc"], item["type"]) for item in error.value.errors()] == [
        (("quality_score",), error_type),
    ]


def test_ai_privacy_persistence_and_cache(monkeypatch):
    captured = []
    report = dict(
        quality_score=90,
        severity="low",
        executive_summary="Good quality.",
        key_issues=[],
        recommended_actions=[],
        business_impact="Ready for review.",
    )

    def fake(summary):
        captured.append(summary)
        return {"report": report}

    monkeypatch.setattr("app.jobs.routes.generate_ai_analysis", fake)
    with TestClient(app) as client:
        result = upload(client, HEADER + "\n" + ROW, "customer-secret.csv")
        url = f"/api/v1/jobs/{result['job_id']}"
        assert client.post(url + "/ai-analysis").json()["report"] == report
        assert client.post(url + "/ai-analysis").json()["report"] == report
        assert client.get(url).json()["ai_report"] == report
    assert len(captured) == 1
    sent = json.dumps(captured)
    assert "alice" not in sent and "C1" not in sent and "customer-secret" not in sent


def test_ai_malformed_response_and_no_key(monkeypatch):
    from app.analytics import ai as llm_analyzer

    monkeypatch.setattr(llm_analyzer, "OPENAI_API_KEY", "")
    assert llm_analyzer.generate_ai_analysis({})["report"] is None
    monkeypatch.setattr(llm_analyzer, "OPENAI_API_KEY", "test-only")
    create = lambda **kwargs: SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content='{"quality_score": 100}'))
        ]
    )
    monkeypatch.setattr(
        llm_analyzer,
        "OpenAI",
        lambda **kwargs: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        ),
    )
    assert llm_analyzer.generate_ai_analysis({})["report"] is None


def test_header_only_and_duplicate_headers_are_persisted_failures():
    with TestClient(app) as client:
        assert upload(client, HEADER + "\n")["status"] == "failed"
        assert upload(client, HEADER + ",email\n")["status"] == "failed"


def test_long_numeric_search_and_case_insensitivity():
    with TestClient(app) as client:
        upload(client, HEADER + "\n" + ROW, "MixedCase.csv")
        assert client.get("/api/v1/jobs?search=mixedcase").json()["total"] == 1
        assert client.get("/api/v1/jobs?search=" + "9" * 100).json()["total"] == 0


def test_non_utf8_is_a_persisted_failure():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/uploads", files={"file": ("broken.csv", b"\xff\xfe", "text/csv")}
        )
        assert response.status_code == 202
        process_job_task.apply(args=[response.json()["job_id"]], throw=True)
        assert client.get(response.json()["status_url"]).json()["status"] == "failed"
        assert client.get("/api/v1/jobs?status=failed").json()["total"] == 1
