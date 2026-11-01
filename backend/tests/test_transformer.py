from app.intake.validation import transform_row


def test_transform_row() -> None:
    row = {
        "customer_id": " cust-001 ",
        "email": "  ALICE@EXAMPLE.COM ",
        "country": " de ",
        "signup_date": "2026-04-01",
        "order_amount": "125.5",
        "currency": " eur ",
        "payment_method": " CARD ",
        "order_status": " COMPLETED ",
        "product_category": " electronics ",
        "quantity": "2",
        "discount_percent": "10",
        "last_login_date": "2026-04-10",
    }

    transformed = transform_row(row)

    assert transformed == {
        "customer_id": "CUST-001",
        "email": "alice@example.com",
        "country": "DE",
        "signup_date": "2026-04-01",
        "order_amount": "125.50",
        "currency": "EUR",
        "payment_method": "card",
        "order_status": "completed",
        "product_category": "electronics",
        "quantity": "2",
        "discount_percent": "10.00",
        "last_login_date": "2026-04-10",
    }
