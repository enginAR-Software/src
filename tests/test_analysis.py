"""Pilot statistics use individual plots, not precomputed treatment means."""

import unittest
from pathlib import Path

from fieldshift_data.analysis import descriptive, mean_difference, prepare
from fieldshift_data.tables import read_zip_csv


class StatisticsTests(unittest.TestCase):
    def test_sample_standard_deviation_and_missingness(self):
        result = descriptive(["1", "2", "3", "NA", "Not measured"])
        self.assertEqual((result["n_total"], result["n_numeric"], result["n_missing"], result["n_unparsed"]), (5, 3, 1, 1))
        self.assertEqual(result["mean"], 2)
        self.assertEqual(result["median"], 2)
        self.assertEqual(result["sd_sample"], 1)

    def test_one_or_no_observation_does_not_imply_zero_variability(self):
        self.assertIsNone(descriptive(["4"])["sd_sample"])
        self.assertIsNone(descriptive(["NA"])["mean"])

    def test_difference_direction_and_percent_units(self):
        a = {"siteid": "A", "indicator": "soc", "unit": "%", "method": "M", "mean": 1.5, "n_numeric": 4}
        b = {**a, "mean": 1.7}
        difference = mean_difference(a, b)
        self.assertAlmostEqual(difference["difference_b_minus_a"], 0.2)
        self.assertEqual(difference["difference_unit"], "percentage_points")

    def test_incompatible_comparisons_rejected(self):
        a = {"siteid": "A", "indicator": "P", "unit": "mg/kg", "method": "Olsen", "mean": 1, "n_numeric": 4}
        for changed in ({"siteid": "B"}, {"method": "Mehlich 3"}, {"unit": "%"}):
            with self.assertRaises(ValueError):
                mean_difference(a, {**a, **changed})

    def test_kansas_and_oregon_keep_phase_and_individual_identity(self):
        root = Path(__file__).resolve().parents[1]
        tables = read_zip_csv(root / "data/raw/napeshm/v1/NAPESHM_public_dataset_06032024.zip")
        data, metrics = prepare(tables, root / "config/pilots.json")
        self.assertEqual(metrics["selected_plots"], 36)
        self.assertEqual(metrics["summary_rows"], 81)
        self.assertEqual(metrics["contrast_rows"], 108)
        self.assertEqual(metrics["pilots"]["kansas"]["crop_phase"], "Sorghum")
        self.assertEqual(len({r["euid"] for r in data["pilot_plots"]}), 36)
        self.assertTrue(all(r["value"] is None for r in data["pilot_plots"] if r["value_status"] == "missing"))


if __name__ == "__main__":
    unittest.main()
