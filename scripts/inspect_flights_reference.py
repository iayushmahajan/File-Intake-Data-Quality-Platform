"""OFFLINE EVALUATION ONLY: aggregate reference integrity, never candidate selection."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

from inspect_flights import (
    HEADER, REPOSITORY, TIME_FIELDS, identity_summary, observed_path, read_flights,
)


def inspect_alignment(root: Path, reference: Path) -> dict:
    dirty_path = observed_path(root)
    reference = reference.absolute()
    resolved = reference.resolve(strict=True)
    if (resolved != reference or REPOSITORY in resolved.parents
            or resolved.name != "clean.csv" or resolved.parent.name != "reference"):
        raise ValueError("Reference must be an external reference/clean.csv without symlinks")
    dirty, dirty_metadata = read_flights(dirty_path)
    clean, clean_metadata = read_flights(resolved)
    dirty_ids = identity_summary(dirty, "tuple_id")
    clean_ids = identity_summary(clean, "tuple_id")
    dirty_counts = Counter(row["tuple_id"] for row in dirty if row["tuple_id"].strip())
    clean_counts = Counter(row["tuple_id"] for row in clean if row["tuple_id"].strip())
    # Never silently pick a first/last row for a duplicate key.
    unique_dirty = {row["tuple_id"]: row for row in dirty
                    if dirty_counts[row["tuple_id"]] == 1}
    unique_clean = {row["tuple_id"]: row for row in clean
                    if clean_counts[row["tuple_id"]] == 1}
    joined = sorted(unique_dirty.keys() & unique_clean.keys())
    identity_mismatches = {
        field: sum(unique_dirty[key][field] != unique_clean[key][field] for key in joined)
        for field in ("src", "flight")
    }
    groups = defaultdict(list)
    for row in clean:
        if row["flight"].strip():
            groups[row["flight"]].append(row)
    differences = {
        field: sum(unique_dirty[key][field] != unique_clean[key][field] for key in joined)
        for field in HEADER
    }
    bijective = (
        all(summary["missing_or_whitespace_rows"] == 0 and summary["duplicate_keys"] == 0
            for summary in (dirty_ids, clean_ids))
        and dirty_counts.keys() == clean_counts.keys()
    )
    return {
        "report_version": 1,
        "evaluation_only": True,
        "comparison": "Exact decoded strings; no normalization; unique tuple_id join",
        "dirty": dirty_metadata,
        "reference": clean_metadata,
        "dirty_ids": dirty_ids,
        "reference_ids": clean_ids,
        "joined_unique_rows": len(joined),
        "dirty_keys_without_reference": len(dirty_counts.keys() - clean_counts.keys()),
        "reference_keys_without_dirty": len(clean_counts.keys() - dirty_counts.keys()),
        "identity_mismatches": identity_mismatches,
        "tuple_id_alignment_valid": bijective and not any(identity_mismatches.values()),
        "row_order_ids_equal": [r["tuple_id"] for r in dirty] == [r["tuple_id"] for r in clean],
        "observation_fields": list(TIME_FIELDS),
        "raw_differing_cells_by_field": differences,
        "raw_differing_time_cells": sum(differences[field] for field in TIME_FIELDS),
        "reference_missing_empty_strings": {
            field: sum(row[field] == "" for row in clean) for field in HEADER
        },
        "reference_whitespace_only_nonempty": {
            field: sum(row[field] != "" and not row[field].strip() for row in clean)
            for field in HEADER
        },
        "reference_groups_multiple_nonempty_raw_values": {
            field: sum(len({row[field] for row in claims if row[field] != ""}) > 1
                       for claims in groups.values()) for field in TIME_FIELDS
        },
        "reference_groups_empty_and_nonempty": {
            field: sum(any(row[field] == "" for row in claims)
                       and any(row[field] != "" for row in claims)
                       for claims in groups.values()) for field in TIME_FIELDS
        },
        "reference_missing_flight_rows": sum(not row["flight"].strip() for row in clean),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect_alignment(args.benchmark_root, args.reference)
    except (OSError, ValueError, csv.Error):
        parser.exit(2, "Alignment inspection failed: check explicit external inputs and CSV structure.\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
