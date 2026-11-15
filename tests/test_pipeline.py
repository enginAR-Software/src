"""Integration against the included, checksum-verified public releases."""

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fieldshift_data.catalog import SOURCES
from fieldshift_data.download import verify_file
from fieldshift_data.pipeline import run
from fieldshift_data.tables import read_csv


ROOT = Path(__file__).resolve().parents[1]


class DownloadIntegrityTests(unittest.TestCase):
    def test_corrupt_existing_file_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "file.csv"
            path.write_bytes(b"bad")
            spec = {"name": "file.csv", "size": 3, "md5": hashlib.md5(b"abc").hexdigest()}
            with self.assertRaises(ValueError):
                verify_file(path, spec)
            self.assertEqual(path.read_bytes(), b"bad")

    def test_no_implicit_download_for_missing_file(self):
        with self.assertRaises(ValueError):
            verify_file(ROOT / "not-a-file.csv", SOURCES["pflux"]["files"][0])


class RealPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shutil
        cls.temp = tempfile.TemporaryDirectory()
        cls.workspace = Path(cls.temp.name)
        shutil.copytree(ROOT / "data/raw", cls.workspace / "data/raw")
        cls.output, cls.metrics = run(cls.workspace)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_source_counts_and_no_event_join_multiplication(self):
        nap = self.metrics["napeshm"]
        self.assertEqual((nap["sites"], nap["treatments"], nap["soil_plots"]), (94, 508, 1453))
        with sqlite3.connect(self.output / "fieldshift_data.sqlite3") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM napeshm_soil_with_context").fetchone()[0], 1453)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM napeshm_soil_indicators").fetchone()[0], 1453 * 9)
        self.assertEqual(nap["management_invalid_links"], 0)

    def test_rotation_positions_and_summaries_are_separate(self):
        p = self.metrics["pflux"]
        self.assertEqual((p["source_rows"], p["systems"]), (224, 61))
        self.assertEqual(p["rotation_position_rows"], 163)
        self.assertEqual(p["system_summary_rows"], 61)
        self.assertEqual(p["reference_footnotes"], 11)
        self.assertEqual(p["unmatched_rotation_reference_rows"], 0)

    def test_observed_canola_soy_wheat_system_budget(self):
        # Independent arithmetic from the official system-level source row:
        # 6.17 applied + .55 atmospheric + 0 irrigation - 3.33 removal = 3.39.
        path = self.output / "processed/pflux/system_comparison.csv"
        rows = read_csv(path.read_bytes(), path.name).rows
        row = next(r for r in rows if r["system_id"] == "AAFC-Sys1")
        self.assertAlmostEqual(float(row["agronomic_calculated"]), 3.39)
        self.assertAlmostEqual(float(row["agronomic_published"]), 3.38)
        self.assertEqual(row["agronomic_check"], "within_rounding")

    def test_incomplete_budgets_remain_missing(self):
        m = self.metrics["pflux"]
        self.assertEqual(m["agronomic_checks"], {"within_rounding": 59, "missing": 2})
        self.assertEqual(m["overall_checks"], {"within_rounding": 45, "missing": 16})
        self.assertEqual(m["nonnumeric_flux_rows"], 1)

    def test_measurement_methods_and_units_survive(self):
        with sqlite3.connect(self.output / "fieldshift_data.sqlite3") as db:
            methods = db.execute("SELECT DISTINCT indicator, unit, method FROM napeshm_soil_indicators WHERE indicator IN ('b_p_m3','b_p_olsen','b_total_n')").fetchall()
        self.assertIn(("b_p_m3", "mg/kg", "Mehlich 3 extract"), methods)
        self.assertIn(("b_p_olsen", "mg/kg", "Olsen extract"), methods)
        self.assertIn(("b_total_n", "%", "Dry Combustion"), methods)

    def test_completed_manifest_and_provenance(self):
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["data_mode"], "real_public_source")
        for dataset in manifest["datasets"]:
            for file in dataset["files"]:
                self.assertEqual(len(file["sha256"]), 64)
        self.assertTrue((self.output / "REPORT.md").is_file())

    def test_wheat_cohort_includes_broad_summary_names(self):
        with sqlite3.connect(self.output / "fieldshift_data.sqlite3") as db:
            rows = db.execute("SELECT system_id, wheat_evidence FROM pflux_wheat_system_comparison").fetchall()
        self.assertEqual(len(rows), 23)
        self.assertIn(("AAFC-Sys4", "rotation_crop_only"), rows)
        self.assertIn(("NC-Sys1", "rotation_crop_only"), rows)

    def test_candidate_site_without_soil_is_explicit(self):
        self.assertEqual(self.metrics["napeshm"]["wheat_sites_with_soil"], 39)
        self.assertEqual(self.metrics["napeshm"]["wheat_sites_without_soil"], ["USWA03"])
        with sqlite3.connect(self.output / "fieldshift_data.sqlite3") as db:
            row = db.execute("SELECT soil_plot_count, has_soil_data FROM napeshm_wheat_site_coverage WHERE sitecode = 'USWA03'").fetchone()
        self.assertEqual(row, (0.0, 0))

    def test_pilot_cli_configuration_and_individual_observations(self):
        result = subprocess.run([sys.executable, "-m", "fieldshift_data", "--workspace", str(self.workspace),
                                 "analyze", "--pilot", "oregon", "--offline"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifests = [p for p in (self.workspace / "outputs").glob("*/manifest.json")
                     if "pilot_analysis" in json.loads(p.read_text())]
        self.assertEqual(len(manifests), 1)
        manifest_path = manifests[0]
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(len(manifest["pilot_analysis"]["config_sha256"]), 64)
        output = manifest_path.parent
        self.assertTrue((output / "PILOT_REPORT.md").is_file())
        with sqlite3.connect(output / "fieldshift_data.sqlite3") as db:
            count = db.execute("SELECT COUNT(DISTINCT euid) FROM analysis_pilot_plots").fetchone()[0]
            stats = db.execute("SELECT n_numeric, mean FROM analysis_pilot_summary WHERE treatmentid='439' AND indicator='b_soc'").fetchone()
            diff = db.execute("SELECT difference_b_minus_a, difference_unit FROM analysis_pilot_contrasts WHERE treatment_a='438' AND treatment_b='439' AND indicator='b_soc'").fetchone()
        self.assertEqual(count, 12)
        self.assertEqual(stats[0], 4)
        self.assertAlmostEqual(stats[1], 1.72560884525)
        self.assertAlmostEqual(diff[0], 0.13844613975)
        self.assertEqual(diff[1], "percentage_points")

    def test_real_planning_cli_and_accounting(self):
        result = subprocess.run([sys.executable, "-m", "fieldshift_data", "--workspace", str(self.workspace),
                                 "plan", "--date", "2028-05-15"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan_file = next((self.workspace / "outputs").glob("plan_*/plan.json"))
        plan = json.loads(plan_file.read_text())
        self.assertEqual(plan["feasible_scenarios"], 5)
        selected = plan["best"][0]
        self.assertEqual([row["crop"] for row in selected["schedule"]], ["Wheat", "Canola", "Soybean"] * 2)
        # Source annual means: wheat 2.02-.22, canola .68-.22, soybean 7.46-.22.
        self.assertAlmostEqual(selected["final_cumulative_p_change"], 19)
        self.assertEqual(plan["data_mode"], "observed_rotation_reference_scenario")
        self.assertIn("day/month", result.stdout)

    def test_cli_query_and_missing_cache(self):
        command = [sys.executable, "-m", "fieldshift_data"]
        result = subprocess.run(command + ["query", str(self.output / "fieldshift_data.sqlite3"), "--system", "AAFC-Sys1"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("within_rounding", result.stdout)
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(command + ["--workspace", folder, "run", "--offline"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((Path(folder) / "outputs").exists())


if __name__ == "__main__":
    unittest.main()
