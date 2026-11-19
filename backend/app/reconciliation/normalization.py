"""Conservative clock interpretation, independent of storage and application startup."""

from dataclasses import dataclass
import re
from typing import Literal

NORMALIZATION_POLICY = "flight_time_normalization_v1"
TimeStatus = Literal["parsed", "missing", "placeholder", "ambiguous", "unsupported"]
Precision = Literal["minute", "second"]

# ASCII digits; no natural-language date parsing or removal of source annotations.
_CLOCK = r"([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?"
_MERIDIEM = re.compile(_CLOCK + r"[ \t]*([ap])\.?[ \t]*m\.?", re.IGNORECASE)
_BARE = re.compile(_CLOCK)
_NOON = re.compile(r"(?:12:00[ \t]*)?noon", re.IGNORECASE)
_CLOCK_COMPONENT = re.compile(r"[0-9]{1,2}:[0-9]{2}")


@dataclass(frozen=True)
class NormalizedTime:
    raw: str
    status: TimeStatus
    canonical_clock: str | None = None
    precision: Precision | None = None
    qualifiers: tuple[str, ...] = ()
    reason: str | None = None
    policy_version: str = NORMALIZATION_POLICY


def normalize_time(raw: str) -> NormalizedTime:
    """Interpret a clock, never a timestamp or an assertion of correctness.

    Bare hours 1–12 lack a period. Bare 0/13–23 establish a 24-hour clock.
    Entire-string matching ensures date/status/offset context is never discarded.
    """
    value = raw.strip()
    if not value:
        return NormalizedTime(raw, "missing", reason=(
            "No source value was supplied." if raw == "" else "Only whitespace was supplied."
        ))
    if value.casefold() in {"not available", "contact airline"}:
        qualifier = "not_available" if value.casefold() == "not available" else "contact_airline"
        return NormalizedTime(raw, "placeholder", qualifiers=(qualifier,),
                              reason="The source explicitly reports unavailable information.")
    if _NOON.fullmatch(value):
        return NormalizedTime(raw, "parsed", "12:00", "minute")
    explicit = _MERIDIEM.fullmatch(value)
    match = explicit or _BARE.fullmatch(value)
    if match:
        hour, minute = int(match[1]), int(match[2])
        second = int(match[3]) if match[3] is not None else None
        precision: Precision = "second" if second is not None else "minute"
        hour_valid = 1 <= hour <= 12 if explicit else 0 <= hour <= 23
        if not hour_valid or minute > 59 or (second is not None and second > 59):
            return NormalizedTime(raw, "unsupported", precision=precision,
                                  reason="Clock components are outside supported ranges.")
        if explicit:
            hour = hour % 12 + (12 if match[4].casefold() == "p" else 0)
        elif 1 <= hour <= 12:
            return NormalizedTime(raw, "ambiguous", precision=precision,
                                  qualifiers=("period_unspecified",),
                                  reason="A bare hour from 1 to 12 does not establish AM or PM.")
        canonical = f"{hour:02d}:{minute:02d}"
        if second is not None:
            canonical += f":{second:02d}"
        return NormalizedTime(raw, "parsed", canonical, precision)
    if _CLOCK_COMPONENT.search(value):
        return NormalizedTime(raw, "unsupported", qualifiers=("uninterpreted_context",),
                              reason="Clock-like text has unsupported context or precision; nothing was discarded.")
    return NormalizedTime(raw, "unsupported", reason="Value is outside the supported clock grammar.")


def equivalent_times(left: NormalizedTime, right: NormalizedTime) -> bool:
    """True only for positively established parsed-clock equivalence in policy v1.

    False means equivalence was not established, not necessarily a disagreement.
    Non-parsed values, even identical strings, are never parsed candidates.
    """
    return (
        left.policy_version == right.policy_version == NORMALIZATION_POLICY
        and left.status == right.status == "parsed"
        and left.canonical_clock is not None
        and left.canonical_clock == right.canonical_clock
        and left.precision == right.precision
        and left.qualifiers == right.qualifiers
    )
