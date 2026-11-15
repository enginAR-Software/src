from datetime import date
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fieldshift_data.climate import PARAMETERS, get, parse, request_definition, summarize


class ClimateTests(unittest.TestCase):
    def fixture(self):
        req = request_definition(dict(sitecode="fixture", site_latitude="40", site_longitude="-100"), date(2027, 1, 1), date(2027, 1, 2), "projection", "ssp245")
        payload = {"header": {"sources": ["NEXGDDP"], "scenarios": ["ssp245"], "model": "ensemble", "fill_value": -999, "time_standard": "UTC",
                              "start": "20270101", "end": "20270102"},
                   "properties": {"parameter": {p: {"ssp245": {"20270101": 1, "20270102": 3}} for p in PARAMETERS}},
                   "parameters": {p: {"units": "mm/day" if p == "PRECTOTCORR" else "C"} for p in PARAMETERS}}
        return req, payload

    def test_scenario_shape_and_complete_precipitation(self):
        request, payload = self.fixture()
        rows = parse(payload, request)
        period, _ = summarize(rows)
        self.assertEqual(period["mean_temperature_c"], 2)
        self.assertEqual(period["precipitation_sum_mm"], 4)

    def test_fill_value_blocks_complete_precipitation_sum(self):
        request, payload = self.fixture()
        payload["properties"]["parameter"]["PRECTOTCORR"]["ssp245"]["20270102"] = -999
        rows = parse(payload, request)
        self.assertIsNone(rows[1]["PRECTOTCORR"])
        period, _ = summarize(rows)
        self.assertIsNone(period["precipitation_sum_mm"])
        self.assertEqual(period["precipitation_days"], 1)

    def test_wrong_scenario_model_or_units_rejected(self):
        request, payload = self.fixture()
        payload["header"]["model"] = "other"
        with self.assertRaises(ValueError):
            parse(payload, request)
        request, payload = self.fixture()
        payload["parameters"]["T2M"]["units"] = "K"
        with self.assertRaises(ValueError):
            parse(payload, request)
        request, payload = self.fixture()
        payload["header"]["scenarios"] = ["ssp370"]
        with self.assertRaises(ValueError):
            parse(payload, request)
        request, payload = self.fixture()
        payload["header"]["time_standard"] = "LST"
        with self.assertRaises(ValueError):
            parse(payload, request)

    def test_projection_cannot_be_loaded_as_historical(self):
        request, payload = self.fixture()
        request["kind"] = "historical"
        with self.assertRaises(ValueError):
            parse(payload, request)

    def test_zero_precipitation_preserved(self):
        request, payload = self.fixture()
        payload["properties"]["parameter"]["PRECTOTCORR"]["ssp245"] = {"20270101": 0, "20270102": 0}
        period, _ = summarize(parse(payload, request))
        self.assertEqual(period["precipitation_sum_mm"], 0)

    def test_cached_climate_integrity_and_no_implicit_network(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            workspace = Path(folder)
            shutil.copytree(root / "data/raw/napeshm", workspace / "data/raw/napeshm")
            with patch("fieldshift_data.climate.request_bytes") as request_bytes:
                with self.assertRaises(ValueError):
                    get(workspace, "USOR03", date(2027, 1, 1), date(2027, 1, 2))
                request_bytes.assert_not_called()
            _, payload = self.fixture()
            with patch("fieldshift_data.climate.request_bytes", return_value=json.dumps(payload).encode()):
                _, _, transfer = get(workspace, "USOR03", date(2027, 1, 1), date(2027, 1, 2), online=True)
            self.assertEqual(transfer, "downloaded")
            with patch("fieldshift_data.climate.request_bytes") as request_bytes:
                _, _, transfer = get(workspace, "USOR03", date(2027, 1, 1), date(2027, 1, 2))
                self.assertEqual(transfer, "cached")
                request_bytes.assert_not_called()
            path = next(p for p in (workspace / "data/raw/nasa_power/projection").glob("*.json") if not p.name.endswith('.receipt.json'))
            path.write_text('{}')
            with self.assertRaises(ValueError):
                get(workspace, "USOR03", date(2027, 1, 1), date(2027, 1, 2))


if __name__ == "__main__":
    unittest.main()
