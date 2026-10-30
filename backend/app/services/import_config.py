import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.intake.schemas import REQUIRED_COLUMNS, ImportOptions
from app.services.validator import get_error_category, validate_row


def suggest_mapping(headers):
    aliases = {
        "customer_id": ["customerid", "customer", "clientid"],
        "email": ["email", "customeremail", "emailaddress"],
        "country": ["country", "countrycode"],
        "signup_date": ["signupdate", "registeredon", "registrationdate"],
        "order_amount": ["orderamount", "amount", "totalamount"],
        "currency": ["currency", "currencycode"],
        "payment_method": ["paymentmethod", "payment"],
        "order_status": ["orderstatus", "status"],
        "product_category": ["productcategory", "category"],
        "quantity": ["quantity", "qty"],
        "discount_percent": ["discountpercent", "discount", "discountpercentage"],
        "last_login_date": ["lastlogindate", "lastlogin"],
    }

    def key(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    result = {}
    for field in REQUIRED_COLUMNS:
        candidates = [h for h in headers if key(h) in aliases[field]]
        result[field] = (
            field if field in headers else candidates[0] if len(candidates) == 1 else ""
        )
    return result


def check_mapping(headers, options: ImportOptions):
    if not headers or len(headers) != len(set(headers)):
        raise ValueError("CSV must have a nonempty header with unique column names")
    if any(not h or len(h) > 200 for h in headers) or len(headers) > 100:
        raise ValueError(
            "CSV headers must be nonempty, at most 200 characters each and 100 columns"
        )
    if options.mapping:
        missing = set(options.mapping.values()) - set(headers)
        if missing:
            raise ValueError(
                "Mapped source columns are missing: " + ", ".join(sorted(missing))
            )


def canonical_row(source, options: ImportOptions):
    mapping = options.mapping or {k: k for k in REQUIRED_COLUMNS}
    return {field: source.get(column) for field, column in mapping.items()}


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


def inspect_csv(path, options=None):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, strict=True)
        headers = reader.fieldnames or []
        check_mapping(headers, options or ImportOptions())
        samples = []
        for row_number, row in enumerate(reader, 2):
            if len(samples) == 10:
                break
            if options is None:
                samples.append(
                    {
                        "row_number": row_number,
                        "values": {h: row.get(h) for h in headers},
                        "issues": [],
                    }
                )
            else:
                values = canonical_row(row, options)
                errors, _ = row_errors(values, row_number, options)
                if None in row or any(v is None for v in row.values()):
                    errors.append("CSV column count does not match header")
                samples.append(
                    {
                        "row_number": row_number,
                        "values": values,
                        "issues": structured_issues(errors),
                    }
                )
        return {
            "headers": headers,
            "required_fields": REQUIRED_COLUMNS,
            "suggested_mapping": suggest_mapping(headers),
            "rows": samples,
            "sample_limit": 10,
        }
