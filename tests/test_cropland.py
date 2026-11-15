import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from fieldshift_data.cropland_source import WHEAT_CLASSES, cached_json, parse_classes, parse_samples, parse_raster
from fieldshift_data.cropland import grid, histories, validate_config


class CroplandTests(unittest.TestCase):
    def points(self):
        return grid({"sitecode": "USOR03", "site_longitude": "-118.624501", "site_latitude": "45.721236"}, 3, .01)

    def sample(self, point, value="24", year=2019, raster=1):
        return {"location": {"x": point["longitude"], "y": point["latitude"], "spatialReference": {"wkid": 4326}},
                "value": value, "rasterId": raster, "resolution": 30, "attributes": {"Year": year}}

    def test_grid_center_and_stable_identity(self):
        points = self.points()
        self.assertEqual(len(points), 9)
        self.assertEqual(points[4]["longitude"], -118.624501)
        self.assertEqual(points[4]["latitude"], 45.721236)
        self.assertEqual(len({p["point_id"] for p in points}), 9)

    def test_reordered_response_joins_by_location_not_position(self):
        points = self.points()[:2]
        payload = {"samples": [self.sample(points[1], "5"), self.sample(points[0])]}
        result = parse_samples(payload, points, 2019, 1)
        self.assertEqual([r["cdl_code"] for r in result], [24, 5])

    def test_background_and_missing_sample_are_unknown_not_negative(self):
        points = self.points()[:2]
        result = parse_samples({"samples": [self.sample(points[0], "0")]}, points, 2019, 1)
        self.assertIsNone(result[0]["cdl_code"])
        self.assertIsNone(result[1]["cdl_code"])
        self.assertEqual(result[0]["status"], "background")
        self.assertEqual(result[1]["status"], "sample_missing")

    def test_wrong_year_raster_coordinates_and_duplicate_rejected(self):
        p = self.points()[:1]
        for samples in ([self.sample(p[0], year=2020)], [self.sample(p[0], raster=2)],
                        [self.sample(self.points()[1])], [self.sample(p[0]), self.sample(p[0])],
                        [self.sample(p[0], "24.5")]):
            with self.assertRaises(ValueError):
                parse_samples({"samples": samples}, p, 2019, 1)

    def test_raster_year_must_be_unique_and_match(self):
        item = {"attributes": {"Year": 2019, "OBJECTID": 1, "Name": "2019_30m_cdls"}}
        self.assertEqual(parse_raster({"features": [item]}, 2019)["OBJECTID"], 1)
        for data in ({"features": []}, {"features": [item, item]}, {"features": [item], "exceededTransferLimit": True}):
            with self.assertRaises(ValueError):
                parse_raster(data, 2019)

    def test_history_missing_year_never_bridges_transition(self):
        rows = [{"sitecode": "x", "point_id": "p", "year": y, "cdl_code": code,
                 "class_name": str(code), "wheat_present": None if code is None else code in (24, 26)}
                for y, code in [(2018, 24), (2019, None), (2020, 5), (2021, 26)]]
        sequences, transitions = histories(rows)
        self.assertFalse(sequences[0]["complete"])
        self.assertEqual(sequences[0]["wheat_years"], 2)
        self.assertEqual(len(transitions), 1)
        self.assertEqual((transitions[0]["from_year"], transitions[0]["to_year"]), (2020, 2021))

    def test_config_blocks_changed_resolution_and_unbounded_requests(self):
        good = {"sites": ["USOR03", "USKS01"], "years": [2018, 2023], "grid_side": 5, "step_degrees": .01}
        validate_config(good)
        for change in ({"years": [2018, 2024]}, {"grid_side": 100}, {"step_degrees": 0},
                       {"sites": ["x", "x"]}, {"step_degrees": float('nan')}):
            with self.assertRaises(ValueError):
                validate_config({**good, **change})

    def test_wheat_dictionary_preserves_double_crops_excludes_buckwheat(self):
        classes = {0: "Background", 39: "Buckwheat", **WHEAT_CLASSES}
        data = {"features": [{"attributes": {"Value": code, "Class_Names": label}} for code, label in classes.items()]}
        result = parse_classes(data)
        self.assertEqual(result[39], "Buckwheat")
        self.assertNotIn(39, WHEAT_CLASSES)
        self.assertIn(26, WHEAT_CLASSES)
        data["features"][-1]["attributes"]["Class_Names"] = "changed"
        with self.assertRaises(ValueError):
            parse_classes(data)

    def test_cache_offline_integrity_and_failed_reply_not_committed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("fieldshift_data.cropland_source.request_bytes") as network:
                with self.assertRaises(ValueError):
                    cached_json(tmp, "query", {}, lambda x: x)
                network.assert_not_called()
            with patch("fieldshift_data.cropland_source.request_bytes", return_value=b'{"error":{"code":498}}'):
                with self.assertRaises(ValueError):
                    cached_json(tmp, "query", {}, lambda x: x, True)
            self.assertEqual(list(Path(tmp).rglob('*.json')), [])
            with patch("fieldshift_data.cropland_source.request_bytes", return_value=b'{"ok":true}'):
                _, receipt = cached_json(tmp, "query", {}, lambda x: x, True)
                self.assertEqual(receipt["transfer"], "downloaded")
            _, receipt = cached_json(tmp, "query", {}, lambda x: x)
            self.assertEqual(receipt["transfer"], "cached")
            path = next(p for p in Path(tmp).rglob('*.json') if 'receipt' not in p.name)
            path.write_text('{}')
            with self.assertRaises(ValueError):
                cached_json(tmp, "query", {}, lambda x: x)
            self.assertEqual(path.read_text(), '{}')

    def test_real_public_cli_links_without_duplicating_soil(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            shutil.copytree(root / "data/raw", workspace / "data/raw")
            run = subprocess.run([sys.executable, "-m", "fieldshift_data", "--workspace", str(workspace),
                                  "cropland", "--offline"], cwd=root, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            output = next((workspace / "outputs").glob('cropland_*'))
            report = json.loads((output / "cropland.json").read_text())
            self.assertEqual(report["observations"], 300)
            self.assertEqual(report["wheat_observations"], 64)
            self.assertEqual(report["points"], 50)
            self.assertEqual(report["adjacent_year_transitions"], 250)
            self.assertEqual(report["soil_plot_count"], 36)
            self.assertEqual(report["soil_indicator_rows"], 324)
            self.assertEqual(report["spatial_context_groups"], 2)
            self.assertFalse(report["model_ready"])
            self.assertTrue(all(r["transfer"] == "cached" for r in report["provenance"]))
            self.assertEqual(len(report["provenance"]), 20)
            self.assertTrue((output / report["climate_report_file"]).is_file())
            points = json.loads((output / "crop_samples.geojson").read_text())["features"]
            self.assertEqual(len(points), 300)
            center = next(p for p in points if p["properties"]["sitecode"] == "USOR03" and
                          p["properties"]["is_center"] and p["properties"]["year"] == 2019)
            self.assertEqual(center["properties"]["cdl_code"], 24)
            self.assertEqual(center["properties"]["soil_assignment"], "site_context_only")


if __name__ == "__main__":
    unittest.main()
