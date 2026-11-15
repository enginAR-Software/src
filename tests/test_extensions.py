"""0.9.0: corridor parcels, rotation effect, climate-to-yield model and MODIS NDVI indicator.

All numbers are FOR TESTS ONLY (synthetic); they are never used as package inputs.
"""

import csv
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
import urllib.parse

from fieldshift_data import economics, geo, goal, satellite, yieldmodel
from fieldshift_data.tables import digest

ROOT = Path(__file__).resolve().parent.parent


def cache_json(folder, url, payload):
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    (folder / f"{key}.json").write_text(json.dumps(payload))
    (folder / f"{key}.receipt.json").write_text(json.dumps({"url": url, "sha256": digest(folder / f"{key}.json")}))


class CorridorParcelTests(unittest.TestCase):
    def write_corridor(self, ws, with_sequence=True):
        out = ws / "outputs" / "corridor_x"
        out.mkdir(parents=True)
        with (out / "corridor_cells.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["cell_id", "longitude", "latitude", "suitable_future"])
            w.writeheader()
            w.writerow({"cell_id": "c04_03", "longitude": -97.5, "latitude": 38.5, "suitable_future": 1})
            w.writerow({"cell_id": "c04_09", "longitude": -97.5, "latitude": 44.5, "suitable_future": 0})
        fields = ["cell_id", "point_id", "longitude", "latitude", "label"] + (["cdl_years", "cdl_sequence"] if with_sequence else [])
        with (out / "corridor_points.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            base = {"longitude": -97.5, "latitude": 38.5, "label": 1}
            rows = [{"cell_id": "c04_03", "point_id": "c04_03:p11", **base, "cdl_sequence": "Winter Wheat → Sorghum → Winter Wheat → Sorghum → Winter Wheat"},
                    {"cell_id": "c04_03", "point_id": "c04_03:p12", **base, "cdl_sequence": "Winter Wheat → Grassland/Pasture → Corn → Corn → Corn"},
                    {"cell_id": "c04_09", "point_id": "c04_09:p11", "longitude": -97.5, "latitude": 44.5, "label": 1,
                     "cdl_sequence": "Corn → Soybeans → Corn → Soybeans → Corn"}]
            for r in rows:
                r["cdl_years"] = "2019-2023"
                if not with_sequence:
                    r.pop("cdl_years"); r.pop("cdl_sequence")
                w.writerow(r)
        return out

    def test_parcels_only_in_future_suitable_cells_with_crop_classes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            out = self.write_corridor(ws)
            parcels, note = goal.corridor_parcels_from_output(ws, out, {"source": "corridor_grid", "shift": {"distance_km": 1}}, 2027, 6)
            self.assertIsNone(note)
            self.assertEqual([p["parcel_id"] for p in parcels], ["c04_03:p11"])
            p = parcels[0]
            self.assertEqual((p["region"], p["site"], p["kind"]), ("KS", "cell:c04_03", "corridor"))
            self.assertEqual(p["previous_crop"], "Winter Wheat")
            self.assertEqual(len(p["current_projection"]), 6)

    def test_old_corridor_output_gives_regeneration_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            out = self.write_corridor(ws, with_sequence=False)
            parcels, note = goal.corridor_parcels_from_output(ws, out, {"source": "corridor_grid", "shift": {"distance_km": 1}}, 2027, 6)
            self.assertEqual(parcels, [])
            self.assertIn("corridor --offline", note)

    def test_state_lookup(self):
        self.assertEqual(geo.state_of(-96.6, 39.2), "KS")
        self.assertEqual(geo.state_of(-118.8, 45.7), "OR")
        self.assertIsNone(geo.state_of(-40.0, 30.0))


class RotationEffectTests(unittest.TestCase):
    CONFIG = {"years": 2, "max_consecutive_same_crop": 2, "min_wheat_seasons": 0, "p_fertilizer_price_usd_per_kg_p": 0.0,
              "rotation_effects": [{"region": "R", "previous": "Winter Wheat", "crop": "Winter Wheat", "yield_multiplier": 0.5}]}
    INPUTS = {("R", "Winter Wheat"): {"yield": 100.0, "price": 1.0, "cost": 0.0},
              ("Q", "Winter Wheat"): {"yield": 100.0, "price": 1.0, "cost": 0.0}}
    P = {"Winter Wheat": {"kg_p_per_ha": 0.0}}

    def test_effect_applies_only_in_its_region_and_after_wheat(self):
        self.assertEqual(economics.year_profit("R", "Winter Wheat", "Winter Wheat", self.INPUTS, self.CONFIG, self.P)[0], 50.0)
        self.assertEqual(economics.year_profit("R", "Winter Wheat", "Sorghum", self.INPUTS, self.CONFIG, self.P)[0], 100.0)
        self.assertEqual(economics.year_profit("Q", "Winter Wheat", "Winter Wheat", self.INPUTS, self.CONFIG, self.P)[0], 100.0)

    def test_price_factor_scales_revenue(self):
        self.assertEqual(economics.year_profit("Q", "Winter Wheat", None, self.INPUTS, self.CONFIG, self.P, 1.2)[0], 120.0)

    def test_package_rotation_effect_is_sourced(self):
        config = json.loads((ROOT / "config/economics.json").read_text(encoding="utf-8"))
        for effect in config["rotation_effects"]:
            self.assertTrue(effect.get("source"))
            self.assertLess(effect["yield_multiplier"], 1.0)


class YieldModelTests(unittest.TestCase):
    def cells(self):
        out = []
        for i in range(6):
            for j in range(6):
                tmax = 26 + i * 1.5 + j * 0.3
                row = {"cell_id": f"c{i:02d}_{j:02d}", "block": f"b{i // 2}_{j // 2}", "longitude": -101.5 + i, "latitude": 37.5 + j}
                for period, dt in (("baseline", 0.0), ("future", 1.5)):
                    row.update({f"{period}_t_mean_c": 10 + i + dt, f"{period}_gdd0_annual": 4000 + 200 * i + 300 * dt,
                                f"{period}_tmax_jun_jul_c": tmax + dt, f"{period}_prec_annual_mm": 500 + 40 * j,
                                f"{period}_prec_oct_jun_mm": 350 + 30 * j})
                out.append(row)
        return out

    def test_recovers_heat_penalty_from_county_yields(self):
        cells = self.cells()
        truth = lambda c: 80 - 0.9 * (c["baseline_tmax_jun_jul_c"] - 27) ** 2 + 0.02 * c["baseline_prec_annual_mm"]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            cents = yieldmodel.centroids()
            by_state = {}
            for fips, (lon, lat) in cents.items():
                cell = yieldmodel.cell_of(lon, lat, cells, 0.5)
                if cell:
                    by_state.setdefault(geo.FIPS[fips[:2]], []).append((fips, next(c for c in cells if c["cell_id"] == cell)))
            series = economics.NASS_SERIES["Winter Wheat"]["yield"]
            for state, items in by_state.items():
                args = yieldmodel.county_args("Winter Wheat", state)
                url = "https://quickstats.nass.usda.gov/api/api_GET/?" + urllib.parse.urlencode(args)
                data = [{"short_desc": series, "state_fips_code": f[:2], "county_code": f[2:], "year": str(y), "Value": f"{truth(c):.2f}"}
                        for f, c in items for y in range(2014, 2019)]
                data.append({"short_desc": series, "state_fips_code": "20", "county_code": "998", "year": "2015", "Value": "999"})
                cache_json(ws / "data/raw/nass", url, {"data": data})
            result = yieldmodel.build(ws, cells, online=False, key="", crops=["Winter Wheat"])
            model = result["models"]["Winter Wheat"]
            self.assertEqual(model["status"], "usable")
            self.assertGreater(model["cv"]["r2"], 0.8)
            hot = [c for c in result["changes"] if c["cell_id"].startswith("c05")]
            self.assertTrue(all(c["yield_multiplier"] < 1.0 for c in hot))

    def test_no_cache_offline_reports_instead_of_inventing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = yieldmodel.build(Path(tmp), self.cells(), online=False, key="", crops=["Corn"])
            self.assertEqual(result["models"]["Corn"]["status"], "insufficient_data")
            self.assertEqual(result["changes"], [])
            self.assertTrue(result["problems"])

    def test_parse_county_skips_combined_and_withheld(self):
        series = economics.NASS_SERIES["Corn"]["yield"]
        payload = {"data": [{"short_desc": series, "state_fips_code": "20", "county_code": "161", "year": str(y), "Value": "150"} for y in (2020, 2021, 2022)]
                   + [{"short_desc": series, "state_fips_code": "20", "county_code": "998", "year": "2020", "Value": "120"},
                      {"short_desc": series, "state_fips_code": "20", "county_code": "001", "year": "2020", "Value": "(D)"}]}
        self.assertEqual(yieldmodel.parse_county(payload, series), {"20161": 150.0})


class SatelliteTests(unittest.TestCase):
    def payload(self, dates, peak_doy):
        return {"scale": "0.0001", "subset": [{"band": satellite.BAND, "modis_date": d,
                                               "data": [int((0.15 + 0.6 * math.exp(-((int(d[5:]) - peak_doy) / 35) ** 2)) / satellite.SCALE)]}
                                              for d in dates] + [{"band": satellite.BAND, "modis_date": "A2023999", "data": [-3000]}]}

    def test_dates_and_chunking(self):
        dates = satellite.modis_dates(2023)
        self.assertEqual(len(dates), 23)
        self.assertEqual(str(satellite.calendar("A2023017")), "2023-01-17")

    def test_series_metrics_and_phenology_check(self):
        phenology = json.loads((ROOT / "config/phenology.json").read_text(encoding="utf-8"))["crops"]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            dates = satellite.modis_dates(2023)
            for i in range(0, len(dates), satellite.CHUNK):
                chunk = dates[i:i + satellite.CHUNK]
                cache_json(ws / "data/raw/modis", satellite.request_url(39.2, -96.6, chunk[0], chunk[-1]), self.payload(chunk, 125))
            points, transfers = satellite.series(ws, 39.2, -96.6, 2023)
            self.assertEqual(len(points), 23)
            self.assertEqual(transfers, ["cached"] * 3)
            wheat = satellite.metrics(points, "Winter Wheat", phenology)
            self.assertEqual(wheat["phenology_check"], "consistent")
            self.assertEqual(wheat["peak_date"][5:7], "05")
            self.assertGreater(wheat["bare_soil_days"], 100)
            self.assertEqual(satellite.metrics(points, "Corn", phenology)["phenology_check"], "inconsistent")
            with self.assertRaises(ValueError):
                satellite.series(ws, 45.0, -100.0, 2023, online=False)

    def test_crop_in_year(self):
        props = {"observed_years": "2019-2023", "observed_sequence": "Corn → Soybeans → Corn → Soybeans → Winter Wheat"}
        self.assertEqual(satellite.crop_in_year(props, 2023), "Winter Wheat")
        self.assertIsNone(satellite.crop_in_year(props, 2018))


if __name__ == "__main__":
    unittest.main()
