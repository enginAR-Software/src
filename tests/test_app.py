"""Tests for the interactive interface (app)."""

import csv
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from fieldshift_data import app, dashboard, goal

ROOT = Path(__file__).resolve().parent.parent


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.workspace = Path(cls.folder.name) / "ws"
        shutil.copytree(ROOT / "data", cls.workspace / "data")
        cls.goal_dir, _ = goal.run(cls.workspace, ROOT / "config/economics.json", ROOT / "config/economics_inputs.csv",
                                   ROOT / "config/crop_calendar.json", ROOT / "config/corridor.json", False)
        dashboard.build(cls.goal_dir, cls.workspace, ROOT / "config/crop_calendar.json")
        cls.page, cls.data = app.build(cls.workspace, cls.goal_dir, ROOT / "config/economics.json",
                                       ROOT / "config/economics_inputs.csv", ROOT / "config/crop_calendar.json")

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_page_is_self_contained(self):
        html = self.page.read_text(encoding="utf-8")
        self.assertNotIn("/*__DATA__*/", html)
        self.assertNotIn("/*__D3__*/", html)
        self.assertNotIn("http://", html.split("<script>")[0])
        self.assertIn("FSOpt", html)
        self.assertIn('"features"', html)

    def test_data_contract(self):
        d = self.data
        self.assertEqual(set(d["components"][i]["key"] for i in range(5)), set("ABCDE"))
        self.assertEqual(len(d["parcels"]), 30)
        for p in d["parcels"]:
            self.assertEqual(len(p["current"]), len(d["plan_years"]))
            self.assertEqual(len(p["observed"]), 6)
        self.assertIn("Winter Wheat", d["windows"]["USKS01"])
        self.assertEqual(d["cells"], [])
        for region in d["regions"].values():
            for entry in region["inputs"].values():
                if entry["yield"] is not None:
                    self.assertTrue(entry["yield_source"])

    @unittest.skipUnless(shutil.which("node"), "Node.js not available")
    def test_browser_optimizer_matches_python(self):
        data_path = Path(self.folder.name) / "app_data.json"
        data_path.write_text(json.dumps(self.data), encoding="utf-8")
        script = r"""
const FSOpt=require(process.argv[1]);const D=JSON.parse(require('fs').readFileSync(process.argv[2]));
const crops={};for(const r in D.regions)crops[r]=D.regions[r].allowed.slice();
const opts={crops,min_wheat:D.params.min_wheat,max_consecutive:D.params.max_consecutive,price_factor:1,use_fallow_rule:true};
const out={};D.parcels.forEach(p=>{const r=FSOpt.strategies(D,p,opts);out[p.id]={most_profitable:r.best,wheat_focused:r.wheat,current:r.current}});
console.log(JSON.stringify(out));"""
        result = subprocess.run(["node", "-e", script, str(ROOT / "fieldshift_data/app_optimizer.js"), str(data_path)],
                                capture_output=True, text=True, check=True)
        js = json.loads(result.stdout)
        with (self.goal_dir / "parcel_strategies.csv").open(encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 90)
        for row in rows:
            plan = js[row["parcel_id"]][row["strategy"]]
            self.assertEqual(" → ".join(plan["sequence"]) if plan else "", row["sequence"], row)
            if row["total_profit_usd_per_acre"]:
                self.assertAlmostEqual(plan["total"], float(row["total_profit_usd_per_acre"]), places=6)
            else:
                self.assertTrue(plan is None or plan["total"] is None)


if __name__ == "__main__":
    unittest.main()


class DemoTests(unittest.TestCase):
    def test_demo_runs_offline_and_reproduces_reference_corridor(self):
        from fieldshift_data import demo
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            shutil.copytree(ROOT / "data", workspace / "data")
            output, page, lines = demo.run(workspace, ROOT / "config/economics.json", ROOT / "config/economics_inputs.csv",
                                           ROOT / "config/crop_calendar.json", ROOT / "config/corridor.json")
            text = "\n".join(lines)
            self.assertTrue(page.is_file())
            self.assertTrue((output / "DEMO.md").is_file())
            self.assertIn("Kansas pilot", text)
            self.assertIn("Oregon pilot", text)
            report = json.loads((output / "goal.json").read_text(encoding="utf-8"))
            zone = report["corridor"]["shift"]["suitable_zone"]
            self.assertEqual((zone["cells_baseline"], zone["cells_future"]), (21, 28))
            self.assertAlmostEqual(report["corridor"]["validation"]["auc"], 0.595, places=3)
            self.assertNotRegex(page.read_text(encoding="utf-8").split("<script>const D")[0], "[çğıöşüÇĞİÖŞÜ]")
