from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NumericProfile(BaseModel):
    count: int
    min: float | None
    max: float | None
    average: float | None


class CategoryCount(BaseModel):
    value: str
    count: int


class Profile(BaseModel):
    numeric: dict[str, NumericProfile] = Field(default_factory=dict)
    categorical: dict[str, list[CategoryCount]] = Field(default_factory=dict)


class Anomaly(BaseModel):
    row: int
    column: str
    value: float
    message: str


class ErrorPattern(BaseModel):
    pattern: str
    count: int


class QualityScore(BaseModel):
    score: float | None
    dimensions: dict[str, float | None] = Field(default_factory=dict)


class AnalysisResponse(BaseModel):
    profiling: Profile = Field(default_factory=Profile)
    quality: QualityScore | None = None
    anomalies: list[Anomaly] = Field(default_factory=list)
    anomaly_count: int = 0
    validation_issue_count: int = 0
    duplicate_records: int = 0
    missing_cells: int = 0
    error_patterns: list[ErrorPattern] = Field(default_factory=list)
    error_preview: list[dict[str, str | None]] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)


class AIReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    quality_score: float = Field(ge=0, le=100)
    severity: Literal["low", "medium", "high"]
    executive_summary: str = Field(min_length=1, max_length=2000)
    key_issues: list[str] = Field(max_length=4)
    recommended_actions: list[str] = Field(max_length=4)
    business_impact: str = Field(min_length=1, max_length=2000)


class AIAnalysisResponse(BaseModel):
    report: AIReport | None = None
    error: str | None = None
