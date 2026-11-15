import csv
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fieldshift_data.alignment import run


ROOT=Path(__file__).resolve().parents[1]


class RealAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.workspace=Path(cls.temp.name)
        shutil.copytree(ROOT/'data/raw/napeshm',cls.workspace/'data/raw/napeshm')
        shutil.copytree(ROOT/'data/raw/nasa_power',cls.workspace/'data/raw/nasa_power')
        with patch('fieldshift_data.climate.request_bytes',side_effect=AssertionError('Unexpected network in offline test')):
            cls.output,cls.readiness=run(cls.workspace)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_source_counts_and_missing_sampling_dates(self):
        self.assertEqual(self.readiness['source_seasons'],26)
        self.assertEqual(self.readiness['aligned_soil_plots'],12)
        self.assertEqual(self.readiness['unlinked_reasons'],{'sampling_date_missing':24})
        self.assertEqual(self.readiness['linked_weather_groups'],1)
        self.assertFalse(self.readiness['dynamic_soil_model_ready'])

    def test_real_season_and_sampling_cutoff(self):
        with sqlite3.connect(self.output/'aligned_data.sqlite3') as db:
            season=db.execute("SELECT sow_date,harvest_date,duration_days,yield_kg_ha FROM observed_seasons WHERE treatmentid='438' AND crop='winter_wheat'").fetchone()
            feature=db.execute("SELECT sampling_date,feature_cutoff,expected_days,documented_explicit_n_kg_ha,complete_weather FROM features_at_sampling WHERE treatmentid='438' LIMIT 1").fetchone()
        self.assertEqual(season,('2018-10-15','2019-07-15',274.0,None))
        self.assertEqual(feature[:3],('2019-04-15','2019-04-14',182.0))
        self.assertAlmostEqual(feature[3],89.6680924955565)
        self.assertEqual(feature[4],1)

    def test_targets_not_features_and_no_future_events(self):
        contract=json.loads((self.output/'training_contract.json').read_text())
        self.assertFalse(set(contract['feature_columns']) & set(contract['target_columns']))
        self.assertFalse(contract['use_for_dynamic_model_training'])
        with (self.output/'management_events.csv').open() as stream:
            events={r['event_id']:r for r in csv.DictReader(stream)}
        with (self.output/'features_at_sampling.csv').open() as stream:
            observations=list(csv.DictReader(stream))
        for row in observations:
            self.assertLess(row['weather_end'],row['sampling_date'])
            for eid in row['event_ids'].split(';'):
                self.assertLess(events[eid]['date'],row['sampling_date'])

    def test_cli_kansas_does_not_invent_soil_dates(self):
        result=subprocess.run([sys.executable,'-m','fieldshift_data','--workspace',str(self.workspace),
                               'seasons','--pilot','kansas','--offline'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('"aligned_soil_plots": 0',result.stdout)
        for path in (self.workspace/'outputs').glob('seasons_*/features_at_sampling.csv'):
            with path.open() as stream:
                reader=csv.DictReader(stream)
                rows=list(reader)
                headers=reader.fieldnames
            if not rows:
                contract=json.loads((path.parent/'training_contract.json').read_text())
                self.assertTrue(set(contract['feature_columns']+contract['target_columns']+[contract['group_column']]) <= set(headers))


if __name__=='__main__':
    unittest.main()
