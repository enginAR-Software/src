from datetime import date
import unittest

from fieldshift_data.seasons import build_seasons, management_features, normalize_amendment, weather_features, sampling_links
from fieldshift_data.alignment import build_observation_rows
from fieldshift_data.napeshm import INDICATORS


def event(day, category, description, unit="", quantity="", tid="1", site="SITE"):
    return dict(treatmentid=tid, sitecode=site, date=day, category=category,
                method="", eventdesc=description, quantity=quantity, unit=unit)


CONFIG = {"soil_campaign_year": 2019, "crop_aliases": {"winter_wheat": ["winter wheat"], "pea": ["pea"]},
          "weather_index_base_c": 0, "weather_index_heat_c": 35}


class SeasonTests(unittest.TestCase):
    def test_cross_year_crop_and_machine_record_separation(self):
        events = [event("2018-10-15", "plant cash crop", "winter wheat", "lbs acre-1 seed", "80"),
                  event("2018-10-15", "plant cash crop", "planter", "STIR", "2.4"),
                  event("2019-07-15", "harvest", "winter wheat", "% residual removed", "0")]
        seasons, _ = build_seasons(events, CONFIG)
        self.assertEqual(len(seasons), 1)
        self.assertEqual(seasons[0]["sow_date"], "2018-10-15")
        self.assertEqual(seasons[0]["harvest_date"], "2019-07-15")
        self.assertIsNone(seasons[0]["yield_kg_ha"])

    def test_explicit_n_is_not_product_mass_seed_or_stir(self):
        explicit = normalize_amendment(event("2018-10-10", "amendment", "fertilizer", "lbs acre-1 N", "80"))
        self.assertAlmostEqual(explicit["explicit_n_kg_ha"], 89.6680925, places=6)
        for unit in ("lbs acre-1", "lbs acre-1 seed", "STIR"):
            self.assertIsNone(normalize_amendment(event("2018-10-10", "amendment", "fertilizer", unit, "80"))["explicit_n_kg_ha"])

    def test_features_stop_at_sampling_and_do_not_use_future_weather(self):
        rows = [dict(date="2019-04-14", T2M=4, T2M_MAX=10, T2M_MIN=-1, PRECTOTCORR=2),
                dict(date="2019-04-15", T2M=6, T2M_MAX=12, T2M_MIN=2, PRECTOTCORR=3),
                dict(date="2019-04-16", T2M=90, T2M_MAX=100, T2M_MIN=80, PRECTOTCORR=100)]
        features = weather_features(rows, date(2019,4,14), date(2019,4,15), CONFIG)
        self.assertEqual(features["precipitation_mm"], 5)
        self.assertEqual(features["thermal_sum_above_base_c_days"], 10)
        self.assertEqual(features["frost_index_days"], 1)

    def test_missing_day_does_not_become_zero_rain(self):
        rows = [dict(date="2019-04-14", T2M=4, T2M_MAX=10, T2M_MIN=2, PRECTOTCORR=0)]
        features = weather_features(rows, date(2019,4,14), date(2019,4,15), CONFIG)
        self.assertIsNone(features["precipitation_mm"])
        self.assertFalse(features["complete_weather"])

    def test_sampling_link_is_within_season_and_requires_explicit_date(self):
        events=[event("2018-10-15", "plant cash crop", "winter wheat"),
                event("2019-04-15", "soil sampling", "NAPESHM"),
                event("2019-07-15", "harvest", "winter wheat")]
        seasons,_=build_seasons(events,CONFIG)
        links=sampling_links(events,seasons,CONFIG)
        self.assertEqual(links["1"]["status"], "linked_treatment_sampling_event")
        self.assertEqual(links["1"]["sampling_date"], "2019-04-15")
        links=sampling_links([e for e in events if e['category']!='soil sampling'],seasons,CONFIG)
        self.assertEqual(links["1"]["status"], "sampling_date_missing")

    def test_sampling_day_and_later_weather_or_fertilizer_not_features(self):
        events=[event("2018-10-15", "plant cash crop", "winter wheat"),
                event("2019-04-14", "amendment", "known N", "lbs acre-1 N", "10"),
                event("2019-04-15", "soil sampling", "NAPESHM"),
                event("2019-04-15", "amendment", "same-day N", "lbs acre-1 N", "20"),
                event("2019-04-16", "amendment", "future N", "lbs acre-1 N", "100"),
                event("2019-07-15", "harvest", "winter wheat")]
        for i,row in enumerate(events):row['event_id']=str(i)
        seasons,_=build_seasons(events,CONFIG)
        links=sampling_links(events,seasons,CONFIG)
        soil=dict(euid='P1',siteid='S1',sitecode='SITE',treatmentid='1',**{i:'1' for i in INDICATORS})
        treatment=dict(eu_tillage='minimum',eu_cover_crops='none',eu_residue='none_removed')
        features,unlinked=build_observation_rows([soil],{'1':treatment},links,seasons,events,{'SITE':[]},CONFIG)
        self.assertFalse(unlinked)
        self.assertEqual(features[0]['feature_cutoff'],'2019-04-14')
        self.assertEqual(features[0]['weather_end'],'2019-04-14')
        self.assertAlmostEqual(features[0]['documented_explicit_n_kg_ha'],11.20851156)
        self.assertNotIn('3',features[0]['event_ids'].split(';'))
        self.assertNotIn('4',features[0]['event_ids'].split(';'))

    def test_multiple_sampling_dates_are_not_assigned_to_same_soil_targets(self):
        events=[event('2018-10-15','plant cash crop','winter wheat'),event('2019-07-15','harvest','winter wheat'),
                event('2019-04-15','soil sampling','NAPESHM'),event('2019-04-16','soil sampling','NAPESHM')]
        seasons,_=build_seasons(events,CONFIG)
        self.assertEqual(sampling_links(events,seasons,CONFIG)['1']['status'],'sampling_date_ambiguous')

    def test_same_day_boundary_n_is_not_counted_twice(self):
        events=[event('2017-03-01','plant cash crop','pea'),event('2017-10-12','harvest','pea'),
                event('2017-10-12','plant cash crop','winter wheat'),event('2018-07-01','harvest','winter wheat'),
                event('2017-10-12','amendment','N','lbs acre-1 N','10')]
        seasons,_=build_seasons(events,CONFIG)
        for season in seasons:
            season['all_ambiguous_boundary_dates']='2017-10-12'
            result=management_features(events,season,date.fromisoformat(season['harvest_date']))
            self.assertEqual(result['documented_explicit_n_kg_ha'],0)
            self.assertEqual(result['unresolved_amendment_count'],1)


if __name__ == "__main__":
    unittest.main()
