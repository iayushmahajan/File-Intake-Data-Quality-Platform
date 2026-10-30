"""Record inspection responses and bounded correction requests."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.intake.schemas import REQUIRED_COLUMNS


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patches: dict[int, dict[str, str]] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def valid_patches(self):
        size = 0
        for row, values in self.patches.items():
            if (
                row < 2
                or row > 2147483647
                or not values
                or set(values) - set(REQUIRED_COLUMNS)
            ):
                raise ValueError(
                    "Corrections must reference data records and known fields"
                )
            for value in values.values():
                if len(value) > 10000:
                    raise ValueError("A corrected cell cannot exceed 10,000 characters")
                size += len(value.encode("utf-8"))
        if size > 1024 * 1024:
            raise ValueError("Correction batch exceeds 1 MiB")
        return self


class RecordResponse(BaseModel):
    row_number: int
    status: str
    values: dict[str, str]
    normalized: dict[str, str]
    issues: list[dict]


class RecordPage(BaseModel):
    records: list[RecordResponse]
    total: int
    page: int
    page_size: int
    fields: list[str]
