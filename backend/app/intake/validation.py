import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict

from app.intake.schemas import REQUIRED_COLUMNS, ImportOptions

ALLOWED_COUNTRIES = {"DE", "FR", "IN", "US", "GB"}
ALLOWED_CURRENCIES = {"EUR", "USD", "INR"}
ALLOWED_PAYMENT_METHODS = {"card", "paypal", "bank_transfer"}
ALLOWED_ORDER_STATUS = {"completed", "pending", "cancelled"}


def validate_csv_columns(fieldnames: list[str] | None) -> tuple[bool, list[str]]:
    if fieldnames is None:
        return False, ["CSV file is missing a header row."]

    if len(fieldnames) != len(set(fieldnames)):
        return False, ["CSV header contains duplicate column names."]

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in fieldnames
    ]

    if missing_columns:
        return False, [f"Missing required columns: {', '.join(missing_columns)}"]

    return True, []


def validate_row(row: dict[str, str], row_number: int) -> list[str]:
    errors: list[str] = []

    customer_id = (row.get("customer_id") or "").strip()
    email = (row.get("email") or "").strip()
    country = (row.get("country") or "").strip().upper()
    signup_date = (row.get("signup_date") or "").strip()
    order_amount_raw = (row.get("order_amount") or "").strip()

    currency = (row.get("currency") or "").strip().upper()
    payment_method = (row.get("payment_method") or "").strip().lower()
    order_status = (row.get("order_status") or "").strip().lower()
    product_category = (row.get("product_category") or "").strip()

    quantity_raw = (row.get("quantity") or "").strip()
    discount_raw = (row.get("discount_percent") or "").strip()
    last_login_date = (row.get("last_login_date") or "").strip()

    amount: Decimal | None = None

    if not customer_id:
        errors.append("customer_id is required")

    if not email:
        errors.append("email is required")
    elif len(email) > 254 or not re.fullmatch(
        r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", email
    ):
        errors.append("email must be valid")

    if not country:
        errors.append("country is required")
    elif country not in ALLOWED_COUNTRIES:
        errors.append("invalid country")

    if not signup_date:
        errors.append("signup_date is required")
    else:
        try:
            datetime.strptime(signup_date, "%Y-%m-%d")
        except ValueError:
            errors.append("invalid signup_date")

    if not order_amount_raw:
        errors.append("order_amount is required")
    else:
        try:
            amount = Decimal(order_amount_raw)
            if not amount.is_finite() or not math.isfinite(float(amount)):
                errors.append("invalid order_amount")
                amount = None
            elif amount < 0:
                errors.append("negative order_amount")
        except InvalidOperation:
            errors.append("invalid order_amount")

    if not currency:
        errors.append("currency is required")
    elif currency not in ALLOWED_CURRENCIES:
        errors.append("invalid currency")

    if not payment_method:
        errors.append("payment_method is required")
    elif payment_method not in ALLOWED_PAYMENT_METHODS:
        errors.append("invalid payment_method")

    if not order_status:
        errors.append("order_status is required")
    elif order_status not in ALLOWED_ORDER_STATUS:
        errors.append("invalid order_status")

    if not product_category:
        errors.append("product_category required")

    if not quantity_raw:
        errors.append("quantity is required")
    else:
        try:
            quantity = int(quantity_raw)
            if not math.isfinite(float(quantity)):
                errors.append("invalid quantity")
            elif quantity <= 0:
                errors.append("quantity must be > 0")
        except (ValueError, OverflowError):
            errors.append("invalid quantity")

    if not discount_raw:
        errors.append("discount_percent is required")
    else:
        try:
            discount = Decimal(discount_raw)
            if not discount.is_finite() or discount < 0 or discount > 100:
                errors.append("invalid discount_percent")
        except InvalidOperation:
            errors.append("invalid discount_percent")

    if not last_login_date:
        errors.append("last_login_date is required")
    else:
        try:
            datetime.strptime(last_login_date, "%Y-%m-%d")
        except ValueError:
            errors.append("invalid last_login_date")

    try:
        if datetime.strptime(last_login_date, "%Y-%m-%d") < datetime.strptime(
            signup_date, "%Y-%m-%d"
        ):
            errors.append("last_login_date precedes signup_date")
    except ValueError:
        pass

    # Repeated customer IDs are legitimate across transactions; do not reject them.
    # Cross-field business rules
    if country in {"DE", "FR"} and currency and currency != "EUR":
        errors.append("currency mismatch for country")

    if order_status == "completed" and amount is not None and amount == 0:
        errors.append("completed order with zero amount")

    return errors


def get_error_category(error: str) -> str:
    if "column count" in error:
        return "CSV Structure"
    if "header" in error or "Missing required columns" in error:
        return "CSV Header"
    if "duplicate record" in error:
        return "Duplicate Record"
    if "last_login_date" in error:
        return "Last Login Date"
    if "customer_id" in error:
        return "Customer ID"

    if "email" in error:
        return "Email"

    if "country" in error or "currency mismatch" in error:
        return "Country / Currency"

    if "signup_date" in error:
        return "Signup Date"

    if "order_amount" in error or "zero amount" in error:
        return "Order Amount"

    if "currency" in error:
        return "Currency"

    if "payment_method" in error:
        return "Payment Method"

    if "order_status" in error:
        return "Order Status"

    if "product_category" in error:
        return "Product Category"

    if "quantity" in error:
        return "Quantity"

    if "discount_percent" in error:
        return "Discount"

    if "last_login_date" in error:
        return "Last Login Date"

    if "Missing required columns" in error or "header row" in error:
        return "CSV Header"

    return "Other"


def transform_row(row: Dict[str, str]) -> Dict[str, str]:
    customer_id = (row.get("customer_id") or "").strip().upper()
    email = (row.get("email") or "").strip().lower()
    country = (row.get("country") or "").strip().upper()

    signup_date_raw = (row.get("signup_date") or "").strip()
    signup_date = datetime.strptime(signup_date_raw, "%Y-%m-%d").strftime("%Y-%m-%d")

    order_amount_raw = (row.get("order_amount") or "").strip()
    order_amount = f"{Decimal(order_amount_raw):.2f}"

    currency = (row.get("currency") or "").strip().upper()
    payment_method = (row.get("payment_method") or "").strip().lower()
    order_status = (row.get("order_status") or "").strip().lower()
    product_category = (row.get("product_category") or "").strip()

    quantity_raw = (row.get("quantity") or "").strip()
    quantity = str(int(quantity_raw))

    discount_raw = (row.get("discount_percent") or "").strip()
    discount_percent = f"{Decimal(discount_raw):.2f}"

    last_login_date_raw = (row.get("last_login_date") or "").strip()
    last_login_date = datetime.strptime(last_login_date_raw, "%Y-%m-%d").strftime(
        "%Y-%m-%d"
    )

    return {
        "customer_id": customer_id,
        "email": email,
        "country": country,
        "signup_date": signup_date,
        "order_amount": order_amount,
        "currency": currency,
        "payment_method": payment_method,
        "order_status": order_status,
        "product_category": product_category,
        "quantity": quantity,
        "discount_percent": discount_percent,
        "last_login_date": last_login_date,
    }


def prepare_row(values, options: ImportOptions):
    result = dict(values)
    for field, rule in options.rules.items():
        if rule.date_format and result.get(field):
            try:
                result[field] = datetime.strptime(
                    result[field].strip(), rule.date_format
                ).strftime("%Y-%m-%d")
            except ValueError:
                # Force base validation to reject a date in the wrong configured format.
                result[field] = "invalid configured date format"
    return result


def row_errors(values, row_number, options: ImportOptions):
    prepared = prepare_row(values, options)
    errors = validate_row(prepared, row_number)
    for field, rule in options.rules.items():
        value = (values.get(field) or "").strip()
        if (
            rule.required
            and not value
            and not any(field in e and "required" in e for e in errors)
        ):
            errors.append(f"{field} is required by template")
        if rule.allowed_values and value.casefold() not in {
            v.strip().casefold() for v in rule.allowed_values
        }:
            errors.append(f"{field} is outside template allowed values")
        if rule.minimum is not None or rule.maximum is not None:
            try:
                number = Decimal(value)
                if number.is_finite():
                    if rule.minimum is not None and number < Decimal(str(rule.minimum)):
                        errors.append(
                            f"{field} is below template minimum {rule.minimum}"
                        )
                    if rule.maximum is not None and number > Decimal(str(rule.maximum)):
                        errors.append(
                            f"{field} exceeds template maximum {rule.maximum}"
                        )
            except InvalidOperation:
                pass  # Base validation already reports malformed numbers.
    return errors, prepared


def structured_issues(errors):
    issues = []
    for message in errors:
        fields = [field for field in REQUIRED_COLUMNS if field in message]
        if "currency mismatch" in message:
            fields = ["country", "currency"]
        if "zero amount" in message:
            fields = ["order_amount", "order_status"]
        issues.append(
            {
                "message": message,
                "fields": fields,
                "category": get_error_category(message),
            }
        )
    return issues
