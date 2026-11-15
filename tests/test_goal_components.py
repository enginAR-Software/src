"""Unit and integration tests for the goal components (A–E).

Numbers in the economics tests are FOR TESTS ONLY (synthetic); they are never used as package inputs.
"""

from datetime import date, timedelta
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest

from fieldshift_data import economics, goal, planting, suitability

ROOT = Path(__file__).resolve().parent.parent


def sinus_year(year, mean=12.0, amplitude=14.0):
    """Synthetic daily temperature: coldest mid-January, warmest mid-July."""
    out = {}
    d = date(year, 1, 1)
    while d.year == year:
        doy = (d - date(year, 1, 1)).days
        out[d] = mean - amplitude * math.cos(2 * math.pi * (doy - 15) / 365.0)
        d += timedelta(days=1)
    return out


class PlantingTests(unittest.TestCase):
    def setUp(self):
        self.calendar = planting.load_calendar(ROOT / "config/crop_calendar.json")

    def test_every_rule_has_sources(self):
        for name, rule in self.calendar["crops"].items():
            self.assertTrue(rule["sources"], name)

    def test_spring_threshold_crossing(self):
        daily = sinus_year(2030)
        result = planting.spring_window(daily, 2030, self.calendar["crops"]["Corn"])
        self.assertEqual(result["status"], "ok")
        three_day = planting.running_mean(daily, result["start"], 3)
        self.assertGreaterEqual(three_day, 10.0)
        self.assertLess(planting.running_mean(daily, result["start"] - timedelta(days=1), 3), 10.0)
        self.assertLess(result["start"], result["end"])

    def test_missing_day_blocks_spring_window(self):
        daily = sinus_year(2030)
        daily[date(2030, 3, 2)] = None
        self.assertEqual(planting.spring_window(daily, 2030, self.calendar["crops"]["Corn"])["status"], "missing_data")

    def test_winter_wheat_uses_previous_autumn_and_gdd(self):
        daily = {**sinus_year(2029), **sinus_year(2030)}
        rule = self.calendar["crops"]["Winter Wheat"]
        result = planting.winter_window(daily, 2030, rule)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["end"].year, 2029)
        gdd = sum(max(daily[result["end"] + timedelta(days=i)], 0) for i in range((date(2029, 12, 31) - result["end"]).days + 1))
        self.assertGreaterEqual(gdd, rule["gdd_by_dec31_c"])
        self.assertEqual((result["end"] - result["start"]).days, rule["early_days"])

    def test_late_december_gap_is_disclosed(self):
        daily = {**sinus_year(2029), **sinus_year(2030)}
        daily[date(2029, 12, 31)] = None
        result = planting.winter_window(daily, 2030, self.calendar["crops"]["Winter Wheat"])
        self.assertEqual(result["status"], "ok")
        self.assertIn("could not be added", result["detail"])
        daily[date(2029, 11, 30)] = None
        self.assertEqual(planting.winter_window(daily, 2030, self.calendar["crops"]["Winter Wheat"])["status"], "missing_data")

    def test_mid_winter_crossing_is_low_confidence(self):
        daily = sinus_year(2030, mean=10.0, amplitude=7.0)
        result = planting.spring_window(daily, 2030, self.calendar["crops"]["Peas"])
        self.assertEqual(result["status"], "low_confidence")

    def test_packaged_nasa_data_gives_oregon_window_around_recorded_sowing(self):
        daily, missing = planting.load_site_daily(ROOT, "USOR03")
        self.assertEqual(missing, [])
        result = planting.window(daily, "Winter Wheat", 2019, self.calendar, {})
        self.assertEqual(result["status"], "ok")
        recorded = date(2018, 10, 15)
        self.assertLessEqual(abs((date.fromisoformat(result["end"]) - recorded).days), 21)


class EconomicsTests(unittest.TestCase):
    def config(self, **extra):
        base = {"plan_start_year": 2027, "years": 4, "max_consecutive_same_crop": 2, "min_wheat_seasons": 1,
                "allowed_crops": {"R": ["Winter Wheat", "Corn"]}, "p_fertilizer_price_usd_per_kg_p": 2.0,
                "p_fertilizer_price_source": "TEST", "fallow_cost_usd_per_acre": 10.0, "fallow_cost_source": "TEST",
                "rotation_effects": []}
        base.update(extra)
        return base

    # SYNTHETIC test inputs
    inputs = {("R", "Winter Wheat"): {"yield": 50.0, "price": 6.0, "cost": 200.0},
              ("R", "Corn"): {"yield": 150.0, "price": 4.0, "cost": 450.0}}
    p_removal = {"Winter Wheat": {"kg_p_per_ha": 12.0}, "Corn": {"kg_p_per_ha": 30.0}}

    def test_year_profit_formula(self):
        profit, missing = economics.year_profit("R", "Corn", None, self.inputs, self.config(), self.p_removal)
        self.assertEqual(missing, [])
        self.assertAlmostEqual(profit, 150 * 4 - 450 - 30 / economics.ACRES_PER_HA * 2.0)

    def test_missing_inputs_are_not_filled(self):
        config = self.config(p_fertilizer_price_usd_per_kg_p=None)
        profit, missing = economics.year_profit("R", "Corn", None, self.inputs, config, self.p_removal)
        self.assertIsNone(profit)
        self.assertIn("P fertilizer price", missing)

    def test_optimizer_respects_constraints_and_is_exhaustive(self):
        ranked, incomplete = economics.optimize("R", ["Winter Wheat", "Corn"], self.inputs, self.config(), self.p_removal)
        self.assertEqual(incomplete, [])
        best = ranked[0]["sequence"]
        self.assertTrue(all(len(set(best[i:i + 3])) > 1 for i in range(len(best) - 2)))
        self.assertGreaterEqual(sum(c == "Winter Wheat" for c in best), 1)
        profits = [r["total_profit_usd_per_acre"] for r in ranked]
        self.assertEqual(profits, sorted(profits, reverse=True))
        # Corn years are more profitable: the best plan must use the two-in-a-row corn limit
        self.assertEqual(best.count("Corn"), 3)

    def test_rotation_effect_changes_choice(self):
        effect = [{"previous": "Winter Wheat", "crop": "Corn", "yield_multiplier": 0.5, "source": "TEST"}]
        ranked, _ = economics.optimize("R", ["Winter Wheat", "Corn"], self.inputs, self.config(rotation_effects=effect), self.p_removal)
        best = ranked[0]["sequence"]
        self.assertFalse(any(a == "Winter Wheat" and b == "Corn" for a, b in zip(best, best[1:])))

    def test_infeasible_transition_excluded(self):
        never = lambda a, b, i: not (a == "Corn" and b == "Winter Wheat")
        ranked, _ = economics.optimize("R", ["Winter Wheat", "Corn"], self.inputs, self.config(), self.p_removal, None, never)
        for r in ranked:
            self.assertFalse(any(a == "Corn" and b == "Winter Wheat" for a, b in zip(r["sequence"], r["sequence"][1:])))

    def test_inputs_require_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "in.csv"
            path.write_text(",".join(economics.INPUT_FIELDS) + "\nR,Corn,150,BU,4,450,,,,\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                economics.load_inputs(path)
            path.write_text(",".join(economics.INPUT_FIELDS) + "\nR,Corn,150,BU,4,450,a,b,c,2020\n", encoding="utf-8")
            self.assertEqual(economics.load_inputs(path)[("R", "Corn")]["yield"], 150.0)

    def test_packaged_inputs_all_have_official_sources(self):
        entries = economics.load_inputs(ROOT / "config/economics_inputs.csv")
        self.assertTrue(entries)
        for key, entry in entries.items():
            for field in ("yield", "price", "cost"):
                if entry[field] is not None:
                    self.assertIn("http", entry[f"{field}_source"], (key, field))
        config = json.loads((ROOT / "config/economics.json").read_text(encoding="utf-8"))
        economics.validate_config(config)
        self.assertIn("http", config["p_fertilizer_price_source"])
        self.assertIn("http", config["fallow_cost_source"])

    def test_fallow_requirement(self):
        config = self.config(fallow_requirement={"R": {"max_years_without_fallow": 2, "source": "TEST"}})
        ok = economics.valid_sequence(["Winter Wheat", "Winter Wheat", "Fallow/Idle Cropland", "Winter Wheat"], config, 1,
                                      lambda a, b, i: True, "R", 0)
        too_long = economics.valid_sequence(["Winter Wheat", "Fallow/Idle Cropland", "Winter Wheat", "Winter Wheat"], config, 1,
                                            lambda a, b, i: True, "R", 0)
        self.assertTrue(ok)
        self.assertTrue(too_long)
        history = economics.valid_sequence(["Winter Wheat", "Fallow/Idle Cropland", "Winter Wheat", "Winter Wheat"], config, 1,
                                           lambda a, b, i: True, "R", 2)
        self.assertFalse(history)
        self.assertFalse(economics.valid_sequence(["Winter Wheat"] * 3 + ["Fallow/Idle Cropland"], self.config(
            max_consecutive_same_crop=3, fallow_requirement={"R": {"max_years_without_fallow": 2, "source": "T"}}), 1,
            lambda a, b, i: True, "R", 0))
        self.assertEqual(economics.years_without_fallow(["Fallow/Idle Cropland", "Winter Wheat", "Peas"]), 2)

    def test_nass_parsing(self):
        series = "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE"
        payload = {"data": [{"short_desc": series, "year": "2020", "Value": "1,150.5"},
                            {"short_desc": series, "year": "2021", "Value": "(D)"}]}
        self.assertEqual(economics.parse_nass(payload, series), {2020: 1150.5})
        with self.assertRaises(ValueError):
            economics.parse_nass({"data": [{"short_desc": "OTHER", "year": "2020", "Value": "1"}]}, series)
        with self.assertRaises(ValueError):
            economics.parse_nass({"error": ["bad request"]}, series)

    def test_nass_key_not_cached_in_url(self):
        args = economics.nass_request("X", {"state_alpha": "KS", "county_name": "RILEY"}, [2014, 2023], "COUNTY")
        self.assertNotIn("key", args)

    def test_manual_overrides_nass(self):
        nass = {("R", "Corn"): {"yield": 100.0, "price": 4.0, "cost": None, "yield_source": "nass", "price_source": "nass", "cost_source": ""}}
        manual = {("R", "Corn"): {"yield": None, "price": 5.0, "cost": 400.0, "unit": "BU", "yield_source": "",
                                  "price_source": "el", "cost_source": "ERS"}}
        merged = economics.merge_inputs(nass, manual)[("R", "Corn")]
        self.assertEqual((merged["yield"], merged["price"], merged["cost"]), (100.0, 5.0, 400.0))

    def test_p_removal_from_pflux(self):
        removal = economics.p_removal_by_crop(ROOT)
        self.assertGreater(removal["Corn"]["systems"], 10)
        self.assertTrue(removal["Corn"]["min"] <= removal["Corn"]["kg_p_per_ha"] <= removal["Corn"]["max"])


class SuitabilityTests(unittest.TestCase):
    def synthetic(self, n=8):
        """SYNTHETIC grid: wheat in cool cells; every cell warms by 2°C in the future."""
        cells, points = [], []
        for j in range(n):
            for i in range(n):
                t = 20 - 1.5 * j
                cell = {"cell_id": f"c{j}{i}", "row": j, "col": i, "latitude": 36 + j, "longitude": -100 + i, "block": f"b{j // 2}{i // 2}",
                        "baseline_ok": True, "future_ok": True}
                for period, dt in (("baseline", 0), ("future", 2)):
                    cell[period] = {"t_mean_c": t + dt, "gdd0_annual": (t + dt) * 365, "tmax_jun_jul_c": t + dt + 15,
                                    "prec_annual_mm": 500 + 10 * i, "prec_oct_jun_mm": 350 + 5 * i}
                cells.append(cell)
                for k in range(3):
                    points.append({"cell_id": cell["cell_id"], "label": int(t + (k - 1) * 0.5 < 12)})
        return cells, points

    def config(self):
        return json.loads((ROOT / "config/corridor.json").read_text(encoding="utf-8"))

    def test_model_trains_validates_and_shifts_north_when_warming(self):
        cells, points = self.synthetic()
        result = suitability.analyse(cells, points, self.config())
        self.assertTrue(result["readiness"]["trained"])
        self.assertGreater(result["validation"]["auc"], 0.8)
        self.assertLess(result["validation"]["brier"], result["validation"]["brier_prevalence_only"])
        bearing = result["shift"]["bearing_deg"]
        self.assertTrue(bearing < 30 or bearing > 330)
        self.assertGreater(result["shift"]["distance_km"], 10)
        zone = result["shift"]["suitable_zone"]
        self.assertGreater(zone["distance_km"], 50)
        self.assertTrue(zone["bearing_deg"] < 30 or zone["bearing_deg"] > 330)
        self.assertGreater(zone["cells_lost"], 0)

    def test_two_sites_are_not_enough(self):
        cells, points = self.synthetic()
        cells = cells[:2]
        points = [p for p in points if p["cell_id"] in {c["cell_id"] for c in cells}]
        result = suitability.analyse(cells, points, self.config())
        self.assertFalse(result["readiness"]["trained"])
        self.assertIsNone(result["model"])

    def test_auc(self):
        self.assertEqual(suitability.auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]), 1.0)
        self.assertEqual(suitability.auc([0.5, 0.5], [0, 1]), 0.5)

    def test_bbox_cells_and_points(self):
        config = self.config()
        cells = suitability.cells_from_bbox(config)
        nx = round(config["bbox"]["east"] - config["bbox"]["west"])
        ny = round(config["bbox"]["north"] - config["bbox"]["south"])
        self.assertEqual(len(cells), nx * ny)
        self.assertEqual(len(suitability.points_for_cell(cells[0], 3, 0.1)), 9)


class GoalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.workspace = Path(cls.folder.name) / "ws"
        shutil.copytree(ROOT / "data", cls.workspace / "data")

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_offline_goal_reports_components_honestly(self):
        empty = Path(self.folder.name) / "empty_inputs.csv"
        empty.write_text(",".join(economics.INPUT_FIELDS) + "\n", encoding="utf-8")
        output, report = goal.run(self.workspace, ROOT / "config/economics.json", empty,
                                  ROOT / "config/crop_calendar.json", ROOT / "config/corridor.json", False)
        self.assertEqual(set(report["status"]), set("ABCDE"))
        self.assertEqual(report["status"]["C"]["status"], "awaiting_inputs")
        self.assertEqual(report["status"]["D"]["status"], "insufficient_training_data")
        self.assertEqual(report["status"]["E"]["status"], "working")
        self.assertGreater(report["parcels"], 0)
        for name in ("GOAL_REPORT.md", "parcel_plans.csv", "parcel_strategies.csv", "planting_windows.csv", "parcels.geojson"):
            self.assertTrue((output / name).is_file(), name)

    def test_goal_with_filled_inputs_produces_three_strategies(self):
        # SYNTHETIC values: only test that the engine runs end to end
        econ = json.loads((ROOT / "config/economics.json").read_text(encoding="utf-8"))
        econ.update({"p_fertilizer_price_usd_per_kg_p": 2.0, "p_fertilizer_price_source": "TEST",
                     "fallow_cost_usd_per_acre": 20.0, "fallow_cost_source": "TEST"})
        econ["allowed_crops"] = {"USKS01": ["Corn", "Soybeans", "Sorghum", "Winter Wheat"], "USOR03": ["Winter Wheat", "Fallow/Idle Cropland"]}
        econ_path = Path(self.folder.name) / "economics.json"
        econ_path.write_text(json.dumps(econ), encoding="utf-8")
        rows = [("USKS01", "Corn", 150, 4.5, 500), ("USKS01", "Soybeans", 45, 11, 300),
                ("USKS01", "Sorghum", 90, 4.2, 300), ("USKS01", "Winter Wheat", 50, 6.5, 230),
                ("USOR03", "Winter Wheat", 60, 6.5, 250)]
        inputs = Path(self.folder.name) / "inputs.csv"
        inputs.write_text(",".join(economics.INPUT_FIELDS) + "\n" + "\n".join(
            f"{r},{c},{y},BU,{p},{k},TEST,TEST,TEST,TEST" for r, c, y, p, k in rows) + "\n", encoding="utf-8")
        output, report = goal.run(self.workspace, econ_path, inputs, ROOT / "config/crop_calendar.json",
                                  ROOT / "config/corridor.json", False)
        self.assertEqual(report["status"]["C"]["status"], "working")
        import csv
        with (output / "parcel_strategies.csv").open(encoding="utf-8") as stream:
            strategies = list(csv.DictReader(stream))
        kansas_best = [r for r in strategies if r["region"] == "USKS01" and r["strategy"] == "most_profitable"]
        self.assertTrue(kansas_best and kansas_best[0]["status"] == "ok")
        oregon = [r for r in strategies if r["region"] == "USOR03" and r["strategy"] == "most_profitable"]
        self.assertTrue(all("Winter Wheat" in r["sequence"] for r in oregon))
        answer = goal.at_date(output, date(2027, 10, 15))
        self.assertTrue(any(r["crop"] == "Winter Wheat" and r["plan_year"] == 2028 for r in answer))


    def test_packaged_official_inputs_respect_oregon_fallow_rule(self):
        output, report = goal.run(self.workspace, ROOT / "config/economics.json", ROOT / "config/economics_inputs.csv",
                                  ROOT / "config/crop_calendar.json", ROOT / "config/corridor.json", False)
        self.assertEqual(report["status"]["C"]["status"], "working")
        import csv
        with (output / "parcel_strategies.csv").open(encoding="utf-8") as stream:
            rows = [r for r in csv.DictReader(stream) if r["region"] == "USOR03" and r["strategy"] == "most_profitable"]
        for row in rows:
            crops = row["sequence"].split(" → ")
            self.assertNotIn("Winter Wheat → Winter Wheat → Winter Wheat", row["sequence"])
            self.assertIn("Fallow/Idle Cropland", crops)


if __name__ == "__main__":
    unittest.main()
