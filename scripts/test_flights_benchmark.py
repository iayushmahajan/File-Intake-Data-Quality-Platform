"""Synthetic standard-library tests; deliberately outside backend conftest scope."""

import ast
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from inspect_flights import HEADER, REPOSITORY, inspect_dirty, read_flights
from inspect_flights_reference import inspect_alignment


def row(key="1", source="source-a", flight="ZZ-1-AAA-BBB", value="08:00"):
    return [key, source, flight, value, "", "09:00", ""]


class FlightsBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.workspace = TemporaryDirectory(prefix="flights-synthetic-")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.dirty = self.root / "observed" / "dirty.csv"
        self.reference = self.root / "reference" / "clean.csv"

    def write_csv(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            writer.writerows(rows)

    def test_reproducible_schema_metadata_and_raw_distributions(self):
        self.write_csv(self.dirty, [row()])
        first = inspect_dirty(self.root)
        self.assertEqual(first, inspect_dirty(self.root))
        self.assertEqual(first["header"], list(HEADER))
        self.assertEqual(first["rows"], 1)
        content = self.dirty.read_bytes()
        self.assertEqual(first["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(first["bytes"], len(content))
        self.assertEqual(first["raw_time_claims"]["sched_dep_time"]["by_flight"],
                         {"ZZ-1-AAA-BBB": {"08:00": 1}})

    def test_quoted_multiline_empty_and_whitespace_remain_raw(self):
        unusual = ' 08:00, "estimated"\nnext line '
        self.write_csv(self.dirty, [row(value=unusual), row("2", value=" ")])
        rows, _ = read_flights(self.dirty)
        self.assertEqual(rows[0]["sched_dep_time"], unusual)
        report = inspect_dirty(self.root)
        self.assertEqual(report["missing_empty_strings"]["act_dep_time"], 2)
        self.assertEqual(report["whitespace_only_nonempty"]["sched_dep_time"], 1)
        self.assertEqual(report["time_format_shapes"]["sched_dep_time"][
            ' N:N, "estimated"\nnext line '], 1)

    def test_missing_duplicate_ids_and_malformed_flight(self):
        self.write_csv(self.dirty, [row(), row(), row(""), row(" ", flight=""),
                                    row("3", flight="bad flight")])
        report = inspect_dirty(self.root)
        self.assertEqual(report["identities"]["tuple_id"], {
            "distinct_nonblank": 2, "missing_or_whitespace_rows": 2,
            "duplicate_keys": 1, "duplicate_excess_rows": 1,
        })
        self.assertEqual(report["identities"]["flight"]["missing_or_whitespace_rows"], 1)
        self.assertEqual(report["flight_shape_nonconforming_rows"], 1)

    def test_repeated_claims_are_not_independent_sources(self):
        self.write_csv(self.dirty, [row(), row("2", value="08:01"),
            row("3", source="source-b"), row("4", flight="ZZ-2-AAA-BBB")])
        report = inspect_dirty(self.root)
        self.assertEqual(report["identities"]["flight"]["distinct_nonblank"], 2)
        self.assertEqual(report["identities"]["src"]["distinct_nonblank"], 2)
        self.assertEqual(report["observations_per_flight"]["ZZ-1-AAA-BBB"], 3)
        self.assertEqual(report["distinct_sources_per_flight"]["ZZ-1-AAA-BBB"], 2)
        self.assertEqual(report["repeated_source_flight_pairs"], 1)
        self.assertEqual(report["repeated_source_flight_excess_rows"], 1)
        self.assertEqual(report["raw_time_claims"]["sched_dep_time"][
            "groups_multiple_nonempty_raw_values"], 1)

    def test_alignment_uses_ids_with_reordered_rows_and_only_emits_aggregates(self):
        self.write_csv(self.dirty, [row(), row("2", value="08:01")])
        self.write_csv(self.reference, [row("2", value="SYNTHETIC-REFERENCE-ONLY"), row()])
        report = inspect_alignment(self.root, self.reference)
        self.assertTrue(report["tuple_id_alignment_valid"])
        self.assertFalse(report["row_order_ids_equal"])
        self.assertEqual(report["joined_unique_rows"], 2)
        self.assertEqual(report["raw_differing_time_cells"], 1)
        self.assertNotIn("SYNTHETIC-REFERENCE-ONLY", json.dumps(report))

    def test_unmatched_duplicate_and_missing_keys_never_silently_align(self):
        self.write_csv(self.dirty, [row(), row("2"), row("3"), row("3"), row("")])
        self.write_csv(self.reference, [row(), row(), row("4"), row(" ")])
        report = inspect_alignment(self.root, self.reference)
        self.assertFalse(report["tuple_id_alignment_valid"])
        self.assertEqual(report["joined_unique_rows"], 0)
        self.assertEqual(report["dirty_keys_without_reference"], 2)
        self.assertEqual(report["reference_keys_without_dirty"], 1)
        self.assertEqual(report["reference_ids"]["duplicate_keys"], 1)
        self.assertEqual(report["reference_ids"]["missing_or_whitespace_rows"], 1)
        self.assertEqual(report["dirty_ids"]["duplicate_keys"], 1)

    def test_identity_mismatch_and_reference_contradictions_are_reported(self):
        self.write_csv(self.dirty, [row(), row("2")])
        self.write_csv(self.reference, [row(source="changed", flight="ZZ-2-AAA-BBB"),
            row("2", flight="ZZ-2-AAA-BBB", value="08:01"),
            row("3", flight="ZZ-2-AAA-BBB", value="")])
        report = inspect_alignment(self.root, self.reference)
        self.assertFalse(report["tuple_id_alignment_valid"])
        self.assertEqual(report["identity_mismatches"], {"src": 1, "flight": 2})
        self.assertEqual(report["reference_groups_multiple_nonempty_raw_values"][
            "sched_dep_time"], 1)
        self.assertEqual(report["reference_groups_empty_and_nonempty"]["sched_dep_time"], 1)

    def test_dirty_inspection_needs_no_reference_and_cannot_read_adjacent_files(self):
        self.write_csv(self.dirty, [row()])
        original = Path.read_bytes
        accessed = []

        def only_dirty(path):
            accessed.append(path)
            if path != self.dirty:
                raise PermissionError("No other benchmark input is accessible")
            return original(path)

        with patch.object(Path, "read_bytes", only_dirty):
            self.assertEqual(inspect_dirty(self.root)["rows"], 1)
        self.assertEqual(accessed, [self.dirty])
        self.assertFalse(self.reference.exists())
        self.write_csv(self.reference, [row(value="SYNTHETIC-REFERENCE-ONLY")])
        accessed.clear()
        with patch.object(Path, "read_bytes", only_dirty):
            self.assertNotIn("SYNTHETIC-REFERENCE-ONLY", json.dumps(inspect_dirty(self.root)))
        self.assertEqual(accessed, [self.dirty])
        self.reference.unlink()
        # Also exercise the actual standalone process with no application imports.
        result = subprocess.run([sys.executable, "-B", str(REPOSITORY / "scripts/inspect_flights.py"),
            "--benchmark-root", str(self.root)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["rows"], 1)

    def test_repository_storage_and_symlink_redirection_are_rejected(self):
        with self.assertRaises(ValueError):
            inspect_dirty(REPOSITORY / "backend/data")
        self.write_csv(self.reference, [row()])
        self.dirty.parent.mkdir()
        self.dirty.symlink_to(self.reference)
        with self.assertRaises(ValueError):
            inspect_dirty(self.root)

    def test_reference_path_is_explicit_and_layout_checked(self):
        self.write_csv(self.dirty, [row()])
        with self.assertRaises(ValueError):
            inspect_alignment(self.root, self.dirty)
        with self.assertRaises(TypeError):
            inspect_alignment(self.root)

    def test_bad_header_width_quoting_encoding_fail_closed(self):
        self.write_csv(self.dirty, [row()[:-1]])
        with self.assertRaises(ValueError):
            inspect_dirty(self.root)
        for content in [b"wrong,header\n", ",".join(HEADER).encode() + b'\n"unterminated',
                        b"\xff"]:
            with self.subTest(content=content):
                self.dirty.write_bytes(content)
                with self.assertRaises((ValueError, csv.Error)):
                    inspect_dirty(self.root)

    def test_bom_is_recorded_without_changing_values(self):
        self.write_csv(self.dirty, [row(value=" 08:00 ")])
        self.dirty.write_bytes(b"\xef\xbb\xbf" + self.dirty.read_bytes())
        records, metadata = read_flights(self.dirty)
        self.assertTrue(metadata["utf8_bom"])
        self.assertEqual(records[0]["sched_dep_time"], " 08:00 ")

    def test_git_and_application_boundaries(self):
        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=REPOSITORY,
                                 capture_output=True, check=True).stdout.decode().split("\0")
        self.assertFalse(any(Path(name).name in {"dirty.csv", "clean.csv"} for name in tracked))
        for name in ["dirty.csv", "clean.csv"]:
            result = subprocess.run(["git", "check-ignore", "--no-index", "--", f"local/{name}"],
                                    cwd=REPOSITORY, capture_output=True)
            self.assertEqual(result.returncode, 0)
        for path in (REPOSITORY / "backend/app").rglob("*.py"):
            tree = ast.parse(path.read_text())
            imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                        for alias in node.names]
            self.assertFalse(any("inspect_flights" in name for name in imports), str(path))
        dirty_source = (REPOSITORY / "scripts/inspect_flights.py").read_text()
        self.assertNotIn("inspect_flights_reference", dirty_source)
        self.assertNotIn("clean.csv", dirty_source)
        self.assertNotIn("app.main", sys.modules)


if __name__ == "__main__":
    unittest.main()
