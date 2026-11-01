"""Bounded, declarative import configuration; never executable expressions."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

REQUIRED_COLUMNS = [
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


class FieldRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required: bool = False
    allowed_values: list[str] = Field(default_factory=list, max_length=100)
    minimum: float | None = None
    maximum: float | None = None
    date_format: Literal["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"] | None = None

    @model_validator(mode="after")
    def valid_bounds(self):
        if any(
            v is not None and not math.isfinite(v) for v in (self.minimum, self.maximum)
        ):
            raise ValueError("Rule bounds must be finite")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("Minimum cannot exceed maximum")
        if any(len(v) > 500 for v in self.allowed_values):
            raise ValueError("Allowed values are limited to 500 characters")
        return self


class ImportOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mapping: dict[str, str] = Field(default_factory=dict)
    rules: dict[str, FieldRule] = Field(default_factory=dict)
    template_id: int | None = Field(default=None, gt=0)
    template_version: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def valid_fields(self):
        if self.mapping:
            if set(self.mapping) != set(REQUIRED_COLUMNS):
                raise ValueError("Map every required field exactly once")
            if any(not v or len(v) > 200 for v in self.mapping.values()):
                raise ValueError("Source column names must contain 1–200 characters")
            if len(set(self.mapping.values())) != len(self.mapping):
                raise ValueError("Each source column can only be mapped once")
        if set(self.rules) - set(REQUIRED_COLUMNS):
            raise ValueError("Unknown field in validation rules")
        for field, rule in self.rules.items():
            if rule.date_format and field not in {"signup_date", "last_login_date"}:
                raise ValueError("Date formats only apply to date fields")
            if (rule.minimum is not None or rule.maximum is not None) and field not in {
                "order_amount",
                "quantity",
                "discount_percent",
            }:
                raise ValueError("Numeric bounds only apply to numeric fields")
        if (self.template_id is None) != (self.template_version is None):
            raise ValueError("Template ID and version must be supplied together")
        return self


class TemplateWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    options: ImportOptions
    expected_version: int | None = Field(default=None, gt=0)
