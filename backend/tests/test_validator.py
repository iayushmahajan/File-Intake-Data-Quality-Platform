from app.intake.validation import validate_csv_columns, validate_row

VALID_COLUMNS = [
    "customer_id",
    "email",
    "country",
    "signup_date",
    "order_amount",
    "currency",
    "payment_method",
    "order_status",
    "product_category",
    "quantity",
    "discount_percent",
    "last_login_date",
]


def test_validate_csv_columns_success() -> None:
    is_valid, errors = validate_csv_columns(VALID_COLUMNS)

    assert is_valid is True
    assert errors == []


def test_validate_csv_columns_missing_order_amount() -> None:
    columns = [column for column in VALID_COLUMNS if column != "order_amount"]

    is_valid, errors = validate_csv_columns(columns)

    assert is_valid is False
    assert errors == ["Missing required columns: order_amount"]


def test_validate_row_success() -> None:
    row = {
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
        "discount_percent": "10",
        "last_login_date": "2026-04-10",
    }

    errors = validate_row(row, row_number=2)

    assert errors == []


def test_validate_row_invalid_values() -> None:
    row = {
        "customer_id": "",
        "email": "wrong-email",
        "country": "ZZ",
        "signup_date": "01-04-2026",
        "order_amount": "-20",
        "currency": "BTC",
        "payment_method": "cash",
        "order_status": "shipped",
        "product_category": "",
        "quantity": "0",
        "discount_percent": "150",
        "last_login_date": "wrong-date",
    }

    errors = validate_row(row, row_number=2)

    assert "customer_id is required" in errors
    assert "email must be valid" in errors
    assert "invalid country" in errors
    assert "invalid signup_date" in errors
    assert "negative order_amount" in errors
    assert "invalid currency" in errors
    assert "invalid payment_method" in errors
    assert "invalid order_status" in errors
    assert "product_category required" in errors
    assert "quantity must be > 0" in errors
    assert "invalid discount_percent" in errors
    assert "invalid last_login_date" in errors
