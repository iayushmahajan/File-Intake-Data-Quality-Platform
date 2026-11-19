"""Pure grouping of intake-validated observations; persisted identity issues are authoritative."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Literal

from app.reconciliation.normalization import NormalizedTime, normalize_time

TimeField = Literal["sched_dep_time", "act_dep_time", "sched_arr_time", "act_arr_time"]
TIME_FIELDS: tuple[TimeField, ...] = (
    "sched_dep_time", "act_dep_time", "sched_arr_time", "act_arr_time",
)


@dataclass(frozen=True)
class ObservationIssue:
    code: str
    field: str | None
    row_number: int | None
    message: str


@dataclass(frozen=True)
class RawObservation:
    """Copy of an intake-validated row, including its complete stored issue metadata."""

    job_id: int
    tuple_id: str
    row_number: int
    src: str
    flight: str
    sched_dep_time: str
    act_dep_time: str
    sched_arr_time: str
    act_arr_time: str
    issues: tuple[ObservationIssue, ...] = ()


@dataclass(frozen=True)
class TimeClaim:
    field: TimeField
    value: NormalizedTime


@dataclass(frozen=True)
class ProjectedObservation:
    raw: RawObservation
    claims: tuple[TimeClaim, ...]


@dataclass(frozen=True)
class SourceReference:
    src: str
    tuple_ids: tuple[str, ...]
    row_numbers: tuple[int, ...]


@dataclass(frozen=True)
class FlightGroup:
    job_id: int
    flight: str
    observations: tuple[ProjectedObservation, ...]

    @property
    def observation_ids(self) -> tuple[str, ...]:
        return tuple(item.raw.tuple_id for item in self.observations)

    @property
    def observation_count(self) -> int:
        return len(self.observations)

    @property
    def source_references(self) -> tuple[SourceReference, ...]:
        by_source = defaultdict(list)
        for item in self.observations:
            row = item.raw
            if row.src.strip() and not any(issue.field == "src" for issue in row.issues):
                by_source[row.src].append(row)
        return tuple(
            SourceReference(src, tuple(row.tuple_id for row in rows),
                            tuple(row.row_number for row in rows))
            for src, rows in sorted(by_source.items())
        )

    @property
    def distinct_source_count(self) -> int:
        return len(self.source_references)


@dataclass(frozen=True)
class UngroupableObservation:
    observation: ProjectedObservation
    reason: Literal["missing_flight", "flagged_flight"]


@dataclass(frozen=True)
class GroupedFlights:
    groups: tuple[FlightGroup, ...]
    ungroupable: tuple[UngroupableObservation, ...]


def group_flights(observations: Iterable[RawObservation]) -> GroupedFlights:
    """Keep every input claim; group by exact (job_id, flight), never infer identity.

    Inputs must carry the identity issues emitted by raha_flights_v1 intake.
    This does not independently validate raw flight syntax or parse new CSVs.
    """
    groups = defaultdict(list)
    ungroupable = []
    seen_ids = set()
    seen_positions = set()
    for row in observations:
        identity, position = (row.job_id, row.tuple_id), (row.job_id, row.row_number)
        if identity in seen_ids or position in seen_positions:
            raise ValueError("Input repeats an observation identity or snapshot position.")
        seen_ids.add(identity)
        seen_positions.add(position)
        projected = ProjectedObservation(row, tuple(
            TimeClaim(field, normalize_time(getattr(row, field))) for field in TIME_FIELDS
        ))
        if not row.flight.strip():
            ungroupable.append(UngroupableObservation(projected, "missing_flight"))
        elif any(issue.field == "flight" for issue in row.issues):
            ungroupable.append(UngroupableObservation(projected, "flagged_flight"))
        else:
            groups[(row.job_id, row.flight)].append(projected)
    return GroupedFlights(
        groups=tuple(FlightGroup(job_id, flight, tuple(sorted(
            rows, key=lambda item: (item.raw.row_number, item.raw.tuple_id)
        ))) for (job_id, flight), rows in sorted(groups.items())),
        ungroupable=tuple(sorted(ungroupable, key=lambda item: (
            item.observation.raw.job_id, item.observation.raw.row_number,
            item.observation.raw.tuple_id,
        ))),
    )
