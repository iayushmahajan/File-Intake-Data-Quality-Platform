"""CSV-extension rejection and shared input for API/async tests."""

import pytest
from app.main import app
from fastapi.testclient import TestClient

VALID_CSV = (
    b"customer_id,email,country,signup_date,order_amount,currency,payment_method,order_status,product_category,quantity,discount_percent,last_login_date\n"
    b"CUST-001,alice@example.com,DE,2026-04-01,125.50,EUR,card,completed,electronics,2,10,2026-04-10\n"
    b"CUST-002,bob@example.com,IN,2026-04-03,89.99,INR,paypal,pending,clothing,1,5,2026-04-09\n"
)


@pytest.mark.parametrize("path", ["/api/v1/uploads", "/api/v1/imports/preview"])
def test_non_csv_upload_and_preview_are_rejected(path) -> None:
    with TestClient(app) as client:
        response = client.post(
            path,
            files={"file": ("sample.txt", b"hello", "text/plain")},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Only CSV files are allowed."}
