"""The narrow raha_flights_v1 raw observation contract. No time interpretation."""

import csv
import hashlib
import io
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import MAX_UPLOAD_BYTES

FLIGHTS_CONTRACT = "raha_flights_v1"
FLIGHTS_VERSION = 1
FLIGHTS_FIELDS = (
    "tuple_id", "src", "flight", "sched_dep_time", "act_dep_time",
    "sched_arr_time", "act_arr_time",
)
# A fingerprint only: never open or configure a path to evaluation labels.
EVALUATION_REFERENCE_SHA256 = "0acfcfd8985b06fdd363965c9e8d9522c43e7589a93d79ae7dc311e1c37fdf3b"


class IntakeIssue(BaseModel):
    code: str
    field: str | None = None
    row_number: int | None = None
    message: str


class FlightObservationData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, from_attributes=True)
    row_number: int
    tuple_id: str
    src: str
    flight: str
    sched_dep_time: str
    act_dep_time: str
    sched_arr_time: str
    act_arr_time: str
    issues: list[IntakeIssue] = Field(default_factory=list)


class FlightsResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["completed"] = "completed"
    observations: list[FlightObservationData]


class FlightsImportError(ValueError):
    def __init__(self, code: str, message: str, row_number=None, field=None):
        self.issue = IntakeIssue(code=code, message=message, row_number=row_number, field=field)
        super().__init__(message)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_reference_hash(digest: str) -> None:
    if digest == EVALUATION_REFERENCE_SHA256:
        raise FlightsImportError("evaluation_reference", "This evaluation-only reference snapshot cannot be imported.")


def process_flights_file(path: Path, expected_sha256: str) -> FlightsResult:
    with path.open("rb") as handle:
        content = handle.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise FlightsImportError("file_size", "Stored input exceeds the configured upload limit.")
    digest = hashlib.sha256(content).hexdigest()
    reject_reference_hash(digest)
    if digest != expected_sha256:
        raise FlightsImportError("input_changed", "Stored input no longer matches the accepted file hash.")
    try:
        text = content.decode("utf-8-sig", errors="strict")
    except UnicodeError as error:
        raise FlightsImportError("encoding", "Flights input must be valid UTF-8.") from error
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    row_number = 1
    try:
        if next(reader, []) != list(FLIGHTS_FIELDS):
            raise FlightsImportError("header", "Expected exactly the seven raha_flights_v1 columns in documented order.", 1)
        observations = []
        seen = set()
        while True:
            row_number += 1
            try:
                values = next(reader)
            except StopIteration:
                break
            if len(values) != len(FLIGHTS_FIELDS):
                raise FlightsImportError("column_count", "CSV record must contain exactly seven cells.", row_number)
            row = dict(zip(FLIGHTS_FIELDS, values))
            # PostgreSQL text cannot represent NUL. Keep bytes, fail publication explicitly.
            if any("\x00" in value for value in values):
                raise FlightsImportError("null_character", "CSV cells cannot contain NUL characters.", row_number)
            if not row["tuple_id"].strip():
                raise FlightsImportError("missing_tuple_id", "Observation identifier must be nonblank.", row_number, "tuple_id")
            if len(row["tuple_id"].encode("utf-8")) > 1024:
                raise FlightsImportError("tuple_id_size", "Observation identifier exceeds 1024 UTF-8 bytes.", row_number, "tuple_id")
            if row["tuple_id"] in seen:
                raise FlightsImportError("duplicate_tuple_id", "Observation identifier occurs more than once.", row_number, "tuple_id")
            seen.add(row["tuple_id"])
            issues = []
            for field in ("src", "flight"):
                value = row[field]
                if not value.strip():
                    issues.append(IntakeIssue(code="blank_identity", field=field,
                        row_number=row_number, message=f"{field} is blank; retain as an identity exception."))
                elif field == "flight" and not re.fullmatch(r"[A-Z0-9]{2,3}-[0-9]+-[A-Z]{3}-[A-Z]{3}", value):
                    issues.append(IntakeIssue(code="flight_shape", field=field,
                        row_number=row_number, message="flight does not match the bounded benchmark key shape."))
                elif field == "src" and (value != value.strip() or any(ord(c) < 32 for c in value)):
                    issues.append(IntakeIssue(code="source_shape", field=field,
                        row_number=row_number, message="src contains surrounding whitespace or control characters."))
            observations.append(FlightObservationData(row_number=row_number, issues=issues, **row))
    except csv.Error as error:
        # Python 3.10 rejects NUL before yielding the parsed cells.
        if str(error) == "line contains NUL":
            raise FlightsImportError("null_character", "CSV cells cannot contain NUL characters.", row_number) from error
        raise FlightsImportError("csv_structure", "Malformed CSV quoting or field size.", row_number) from error
    if not observations:
        raise FlightsImportError("empty_dataset", "CSV contains no observations.")
    return FlightsResult(observations=observations)
