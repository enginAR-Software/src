from datetime import date
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from fieldshift_data.climate import dates
from fieldshift_data.regional import period_statistics, compare, validate_config


def weather(year, temperature, rain):
    return [{"date": day.isoformat(), "T2M": temperature, "PRECTOTCORR": rain}
            for day in dates(date(year, 1, 1), date(year, 12, 31))]


class RegionalTests(unittest.TestCase):
    def test_independent_constant_climate_change(self):
        baseline = period_statistics(weather(2020, 10, 2), 2020, 2020)
        future = period_statistics(weather(2040, 13, 3), 2040, 2040)
        annual, months = compare(baseline, future)
        self.assertEqual(annual["temperature_delta_c"], 3)
        self.assertEqual(annual["annual_precipitation_delta_mm"], 366)
        self.assertEqual(annual["annual_precipitation_delta_percent"], 50)
        self.assertEqual(months[0]["precipitation_delta_mm"], 31)

    def test_missing_day_blocks_annual_but_preserves_complete_months(self):
        rows = weather(2040, 13, 3)
        rows[-1]["PRECTOTCORR"] = None
        baseline = period_statistics(weather(2020, 10, 2), 2020, 2020)
        annual, months = compare(baseline, period_statistics(rows, 2040, 2040))
        self.assertIsNone(annual["annual_precipitation_delta_mm"])
        self.assertEqual(annual["temperature_delta_c"], 3)
        self.assertIsNone(months[-1]["precipitation_delta_mm"])
        self.assertEqual(months[0]["precipitation_delta_mm"], 31)

    def test_omitted_and_duplicate_dates_rejected(self):
        rows = weather(2020, 10, 2)
        with self.assertRaises(ValueError):
            period_statistics(rows[:-1], 2020, 2020)
        with self.assertRaises(ValueError):
            period_statistics(rows + [rows[0]], 2020, 2020)

    def test_missing_entire_year_cannot_disappear_from_mean(self):
        rows = weather(2020, 10, 2) + weather(2021, None, None)
        result = period_statistics(rows, 2020, 2021)
        self.assertIsNone(result["mean_temperature_c"])
        self.assertIsNone(result["mean_annual_precipitation_mm"])
        self.assertEqual(result["complete_temperature_years"], 1)

    def test_zero_baseline_has_no_percent_change(self):
        a = period_statistics(weather(2020, 10, 0), 2020, 2020)
        b = period_statistics(weather(2040, 10, 1), 2040, 2040)
        annual, _ = compare(a, b)
        self.assertIsNone(annual["annual_precipitation_delta_percent"])
        self.assertEqual(annual["annual_precipitation_delta_mm"], 366)

    def test_config_rejects_overlap_unequal_periods_and_duplicates(self):
        good = {"sites": ["USOR03", "USKS01"], "baseline": [2015, 2024],
                "future": [2040, 2049], "scenario": "ssp245"}
        validate_config(good)
        for update in ({"future": [2020, 2029]}, {"future": [2040, 2044]},
                       {"sites": ["USOR03", "USOR03"]}, {"baseline": [2010, 2019]},
                       {"scenario": "ssp585"}):
            with self.assertRaises(ValueError):
                validate_config({**good, **update})

    def test_public_cli_real_cached_data_and_geojson(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            shutil.copytree(root / "data/raw", workspace / "data/raw")
            process = subprocess.run([sys.executable, "-m", "fieldshift_data", "--workspace", str(workspace),
                                      "regional", "--offline"], cwd=root, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            output = next((workspace / "outputs").iterdir())
            report = json.loads((output / "regional.json").read_text())
            self.assertEqual(len(report["provenance"]), 8)
            self.assertTrue(all(p["transfer"] == "cached" for p in report["provenance"]))
            self.assertFalse(report["crop_decision_ready"])
            oregon, kansas = report["sites"]
            self.assertEqual(oregon["complete_monthly_temperature_comparisons"], 11)
            self.assertAlmostEqual(oregon["monthly_change"][6]["temperature_delta_c"], 1.3061935483871)
            self.assertAlmostEqual(kansas["monthly_change"][6]["temperature_delta_c"], 1.10338709677419)
            self.assertIsNone(oregon["annual_change"]["annual_precipitation_delta_mm"])
            self.assertIsNone(oregon["monthly_change"][11]["temperature_delta_c"])
            geojson = json.loads((output / "regional_change.geojson").read_text())
            self.assertEqual(len(geojson["features"]), 2)
            self.assertEqual(geojson["features"][0]["geometry"]["coordinates"], [-118.624501, 45.721236])
            self.assertIsNone(geojson["features"][0]["properties"]["wheat_suitability"])
            self.assertEqual(len(geojson["features"][0]["properties"]["monthly_change"]), 12)
            self.assertAlmostEqual(geojson["features"][0]["properties"]["monthly_change"][6]["temperature_delta_c"], 1.3061935483871)


if __name__ == "__main__":
    unittest.main()
