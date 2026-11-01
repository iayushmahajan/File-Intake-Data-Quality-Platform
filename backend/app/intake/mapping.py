import csv
import re

from app.intake.schemas import REQUIRED_COLUMNS, ImportOptions
from app.intake.validation import row_errors, structured_issues


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
