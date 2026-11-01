import pytest
from app.main import app
from app.tasks import process_job_task
from fastapi.testclient import TestClient

INVALID_CSV = (
    b"customer_id,email,country,signup_date,order_amount,currency,payment_method,order_status,product_category,quantity,discount_percent,last_login_date\n"
    b",wrong-email,ZZ,01-04-2026,-20,BTC,cash,shipped,,0,150,wrong-date\n"
)


def create_invalid_job(client: TestClient, filename: str = "invalid.csv") -> int:
    response = client.post(
        "/api/v1/uploads",
        files={"file": (filename, INVALID_CSV, "text/csv")},
    )

    assert response.status_code == 202
    process_job_task.apply(args=[response.json()["job_id"]], throw=True)
    return response.json()["job_id"]


def test_list_jobs_empty() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/jobs")

    assert response.status_code == 200
    assert response.json() == {"jobs": [], "total": 0, "page": 1, "page_size": 10}


@pytest.mark.parametrize("suffix", ["", "/download/clean", "/download/errors"])
def test_job_and_downloads_return_404_for_unknown_job(suffix) -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/jobs/999999{suffix}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found."}


def test_all_invalid_job_completes_with_downloadable_errors() -> None:
    with TestClient(app) as client:
        job_id = create_invalid_job(client, filename="error_download.csv")
        detail = client.get(f"/api/v1/jobs/{job_id}").json()
        assert detail["status"] == "completed"
        assert (detail["total_rows"], detail["valid_rows"], detail["invalid_rows"]) == (1, 0, 1)
        assert detail["analysis"]["quality"] == {
            "score": 29.6,
            "dimensions": {
                "validity": 0.0, "completeness": 83.33,
                "uniqueness": 100.0, "anomaly_health": None,
            },
        }
        response = client.get(f"/api/v1/jobs/{job_id}/download/errors")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "customer_id is required" in response.text
    assert "email must be valid" in response.text
    assert "invalid country" in response.text
    assert "invalid currency" in response.text
    assert "invalid payment_method" in response.text
