"""Dirty-only Flights inspection. Standard library; never imports the application."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re

HEADER = (
    "tuple_id", "src", "flight", "sched_dep_time", "act_dep_time",
    "sched_arr_time", "act_arr_time",
)
TIME_FIELDS = HEADER[3:]
REPOSITORY = Path(__file__).resolve().parents[1]


def external_root(root: Path) -> Path:
    root = root.resolve(strict=True)
    if not root.is_dir() or root == REPOSITORY or REPOSITORY in root.parents:
        raise ValueError("Benchmark root must be a directory outside the repository")
    return root


def observed_path(root: Path) -> Path:
    path = external_root(root) / "observed" / "dirty.csv"
    if path.resolve(strict=True) != path:
        raise ValueError("Observed input must not redirect through symlinks")
    return path


def read_flights(path: Path) -> tuple[list[dict[str, str]], dict]:
    """Explicit single-file reader, also reused by the offline alignment command.

    No discovery, adjacent-file reads, configuration imports, or value coercion.
    Structural errors fail closed without including cell contents in errors.
    """
    return decode_flights(path.read_bytes())


def decode_flights(content: bytes) -> tuple[list[dict[str, str]], dict]:
    """Decode already bounded/verified bytes without opening any other file."""
    text = content.decode("utf-8-sig", errors="strict")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    header = next(reader, [])
    if header != list(HEADER):
        raise ValueError("Unexpected Flights header or field order")
    rows = []
    for number, values in enumerate(reader, 2):
        if len(values) != len(HEADER):
            raise ValueError(f"CSV record {number} has an unexpected field count")
        rows.append(dict(zip(HEADER, values)))
    return rows, {
        "header": header,
        "rows": len(rows),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "encoding": "UTF-8 (ASCII subset)" if content.isascii() else "UTF-8",
        "utf8_bom": content.startswith(b"\xef\xbb\xbf"),
        "crlf_sequences": content.count(b"\r\n"),
        "lf_bytes": content.count(b"\n"),
        "structural_issues": 0,
    }


def identity_summary(rows: list[dict[str, str]], field: str) -> dict:
    counts = Counter(row[field] for row in rows if row[field].strip())
    return {
        "distinct_nonblank": len(counts),
        "missing_or_whitespace_rows": sum(not row[field].strip() for row in rows),
        "duplicate_keys": sum(count > 1 for count in counts.values()),
        "duplicate_excess_rows": sum(count - 1 for count in counts.values()),
    }


def inspect_dirty(root: Path) -> dict:
    rows, metadata = read_flights(observed_path(root))
    groups = defaultdict(list)
    for row in rows:
        if row["flight"].strip():
            groups[row["flight"]].append(row)
    pairs = Counter((row["flight"], row["src"]) for row in rows
                    if row["flight"].strip() and row["src"].strip())
    conflicts = {}
    for field in TIME_FIELDS:
        distributions = {
            flight: Counter(row[field] for row in claims)
            for flight, claims in sorted(groups.items())
        }
        conflicts[field] = {
            "groups_multiple_raw_values_including_empty": sum(
                len(values) > 1 for values in distributions.values()
            ),
            "groups_multiple_nonempty_raw_values": sum(
                sum(value != "" for value in values) > 1
                for values in distributions.values()
            ),
            "groups_with_empty_and_nonempty": sum(
                "" in values and len(values) > 1 for values in distributions.values()
            ),
            "by_flight": {
                flight: dict(sorted(values.items()))
                for flight, values in distributions.items()
            },
        }
    return {
        "report_version": 1,
        "comparison": "Exact decoded strings; no trimming or time normalization",
        **metadata,
        "identities": {field: identity_summary(rows, field) for field in HEADER[:3]},
        "flight_shape_nonconforming_rows": sum(
            bool(row["flight"].strip()) and not re.fullmatch(
                r"[A-Z0-9]{2,3}-[0-9]+-[A-Z]{3}-[A-Z]{3}", row["flight"]
            ) for row in rows
        ),
        "observations_per_flight": dict(sorted(Counter(
            row["flight"] for row in rows if row["flight"].strip()
        ).items())),
        "observations_per_source": dict(sorted(Counter(
            row["src"] for row in rows if row["src"].strip()
        ).items())),
        "missing_empty_strings": {
            field: sum(row[field] == "" for row in rows) for field in HEADER
        },
        "whitespace_only_nonempty": {
            field: sum(row[field] != "" and not row[field].strip() for row in rows)
            for field in HEADER
        },
        "time_format_shapes": {
            field: dict(sorted(Counter(
                re.sub(r"[0-9]+", "N", row[field]) for row in rows
            ).items())) for field in TIME_FIELDS
        },
        "repeated_source_flight_pairs": sum(count > 1 for count in pairs.values()),
        "repeated_source_flight_excess_rows": sum(count - 1 for count in pairs.values()),
        "distinct_sources_per_flight": {
            flight: len({row["src"] for row in claims if row["src"].strip()})
            for flight, claims in sorted(groups.items())
        },
        "raw_time_claims": conflicts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect_dirty(args.benchmark_root)
    except (OSError, ValueError, csv.Error):
        parser.exit(2, "Inspection failed: check external layout, UTF-8, header and CSV structure.\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
