from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

NUMERIC_COLUMNS = ["order_amount", "quantity", "discount_percent"]
CATEGORICAL_COLUMNS = [
    "country",
    "currency",
    "payment_method",
    "order_status",
    "product_category",
]


def safe_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def get_top_values(
    rows: List[Dict[str, str]], column: str, limit: int = 3
) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}

    for row in rows:
        value = (row.get(column) or "").strip()
        if not value:
            continue

        counts[value] = counts.get(value, 0) + 1

    sorted_values = sorted(counts.items(), key=lambda item: item[1], reverse=True)

    return [{"value": value, "count": count} for value, count in sorted_values[:limit]]


def profile_numeric_column(rows: List[Dict[str, str]], column: str) -> Dict[str, Any]:
    values = [safe_decimal(row.get(column, "")) for row in rows]
    numeric_values = [value for value in values if value is not None]

    if not numeric_values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "average": None,
        }

    total = sum(numeric_values)

    return {
        "count": len(numeric_values),
        "min": float(min(numeric_values)),
        "max": float(max(numeric_values)),
        "average": float(total / len(numeric_values)),
    }


def detect_numeric_anomalies(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    anomalies: List[Dict[str, Any]] = []

    for row_index, row in enumerate(rows, start=1):
        order_amount = safe_decimal(row.get("order_amount", ""))
        quantity = safe_decimal(row.get("quantity", ""))
        discount = safe_decimal(row.get("discount_percent", ""))

        if order_amount is not None and order_amount > Decimal("1000"):
            anomalies.append(
                {
                    "row": row_index,
                    "column": "order_amount",
                    "value": float(order_amount),
                    "message": "High-value order detected.",
                }
            )

        if quantity is not None and quantity > Decimal("20"):
            anomalies.append(
                {
                    "row": row_index,
                    "column": "quantity",
                    "value": float(quantity),
                    "message": "Unusually large quantity detected.",
                }
            )

        if discount is not None and discount > Decimal("50"):
            anomalies.append(
                {
                    "row": row_index,
                    "column": "discount_percent",
                    "value": float(discount),
                    "message": "High discount detected.",
                }
            )

    return anomalies


def group_error_patterns(error_rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    pattern_counts: Dict[str, int] = {}

    for row in error_rows:
        errors = row.get("errors", "")
        if not errors:
            continue

        normalized_pattern = " + ".join(
            sorted(error.strip() for error in errors.split(";") if error.strip())
        )

        pattern_counts[normalized_pattern] = (
            pattern_counts.get(normalized_pattern, 0) + 1
        )

    sorted_patterns = sorted(
        pattern_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    return [
        {
            "pattern": pattern,
            "count": count,
        }
        for pattern, count in sorted_patterns
    ]


def generate_insights(
    total_rows: int,
    valid_rows: int,
    invalid_rows: int,
    error_breakdown: Dict[str, int],
    anomalies: List[Dict[str, Any]],
) -> List[str]:
    insights: List[str] = []

    if total_rows == 0:
        insights.append(
            "No data rows were processed. Check whether the file contains valid CSV rows."
        )
        return insights

    invalid_rate = invalid_rows / total_rows

    if invalid_rate == 0:
        insights.append(
            "All rows passed validation. The file is ready for downstream processing."
        )
    elif invalid_rate >= 0.5:
        insights.append(
            "More than half of the uploaded rows failed validation. This suggests a source-system or export-format issue."
        )
    else:
        insights.append(
            "Some rows failed validation, but most records can still be processed."
        )

    if error_breakdown:
        dominant_category, dominant_count = max(
            error_breakdown.items(),
            key=lambda item: item[1],
        )

        insights.append(
            f"The most frequent issue is related to {dominant_category}, with {dominant_count} occurrence(s)."
        )

    if "Country / Currency" in error_breakdown:
        insights.append(
            "Country and currency mismatches were detected. This may indicate incorrect market mapping in the source data."
        )

    if "Discount" in error_breakdown:
        insights.append(
            "Discount validation errors were found. Review discount rules before using this data for revenue analysis."
        )

    if anomalies:
        insights.append(
            f"{len(anomalies)} potential business anomaly/anomalies were detected in otherwise valid rows."
        )

    return insights


def analyze_processed_data(
    valid_rows: List[Dict[str, str]],
    error_rows: List[Dict[str, str]],
    error_breakdown: Dict[str, int],
) -> Dict[str, Any]:
    total_rows = len(valid_rows) + len(error_rows)
    invalid_rows = len(error_rows)

    profiling = {
        "numeric": {
            column: profile_numeric_column(valid_rows, column)
            for column in NUMERIC_COLUMNS
        },
        "categorical": {
            column: get_top_values(valid_rows, column) for column in CATEGORICAL_COLUMNS
        },
    }

    anomalies = detect_numeric_anomalies(valid_rows)
    error_patterns = group_error_patterns(error_rows)

    insights = generate_insights(
        total_rows=total_rows,
        valid_rows=len(valid_rows),
        invalid_rows=invalid_rows,
        error_breakdown=error_breakdown,
        anomalies=anomalies,
    )

    return {
        "profiling": profiling,
        "error_patterns": error_patterns,
        "anomalies": anomalies,
        "insights": insights,
    }


def calculate_quality(
    total: int,
    valid: int,
    missing: int,
    columns: int,
    duplicates: int,
    anomalous_valid_rows: int,
) -> dict:
    """Score only measured dimensions; an empty dataset has no score."""
    if not total:
        return {"score": None, "dimensions": {}}
    dimensions = {
        "validity": round(100 * valid / total, 2),
        "completeness": round(100 * (1 - missing / (total * columns)), 2),
        "uniqueness": round(100 * (1 - duplicates / total), 2),
        "anomaly_health": round(100 * (1 - anomalous_valid_rows / valid), 2)
        if valid
        else None,
    }
    weights = {
        "validity": 0.6,
        "completeness": 0.2,
        "uniqueness": 0.1,
        "anomaly_health": 0.1,
    }
    available = {key: value for key, value in dimensions.items() if value is not None}
    score = sum(value * weights[key] for key, value in available.items()) / sum(
        weights[key] for key in available
    )
    return {"score": round(score, 1), "dimensions": dimensions}
