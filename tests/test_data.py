"""Behavioral checks; fixtures are synthetic and isolated from real data."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from fieldshift_data.tables import read_csv, read_zip_csv, profile
from fieldshift_data.pflux import budget, reference_index


class DataTests(unittest.TestCase):
    def test_missing_values_are_not_zero(self):
        table = read_csv(b"id,value\n001,0\n002,NA\n003,\n004,2\n", "fixture.csv")
        info = profile(table)
        value = next(c for c in info["columns"] if c["name"] == "value")
        self.assertEqual(value["missing"], 2)
        self.assertEqual(value["numeric_count"], 2)
        self.assertEqual(value["mean"], 1)
        self.assertEqual(table.rows[0]["id"], "001")

    def test_duplicate_header_and_wrong_width_rejected(self):
        for content in (b"a,a\n1,2\n", b"a,b\n1,2,3\n"):
            with self.assertRaises(ValueError):
                read_csv(content, "bad.csv")

    def test_archive_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            nested = Path(folder) / "nested"
            nested.mkdir()
            path = nested / "bad.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.csv", "a\n1\n")
            with self.assertRaises(ValueError):
                read_zip_csv(path)
            self.assertFalse((Path(folder) / "escape.csv").exists())

    def test_p_balance_independent_arithmetic(self):
        result = budget(dict(application=10, deposition=0.5, irrigation=0,
                             removal=8, surface=0.2, subsurface=0.1))
        self.assertAlmostEqual(result["agronomic"], 2.5)
        self.assertAlmostEqual(result["overall"], 2.2)

    def test_missing_flux_blocks_budget(self):
        result = budget(dict(application=None, deposition=0.5, irrigation=0,
                             removal=8, surface=0.2, subsurface=0.1))
        self.assertIsNone(result["agronomic"])
        self.assertIsNone(result["overall"])
        result = budget(dict(application=10, deposition=0.5, irrigation=0,
                             removal=8, surface=None, subsurface=0.1))
        self.assertEqual(result["agronomic"], 2.5)
        self.assertIsNone(result["overall"])

    def test_reference_footnotes_are_preserved_without_joining_as_data(self):
        table = read_csv(b"Location,Cropping system ID,Rotation year,Notes\nA,S1,1,source\n,,,footnote1\n,,,footnote2\n", "references.csv")
        indexed, notes = reference_index(table)
        self.assertEqual(len(indexed), 1)
        self.assertEqual(len(notes), 2)


if __name__ == "__main__":
    unittest.main()
