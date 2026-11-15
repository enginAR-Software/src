# FieldShift goal report

**Project goal (Preparation.md):** Using a range of data, estimate the most suitable region that North American wheat will migrate to under climate change; train a mathematical model that computes the economically most efficient crop rotation for the regions split into parcels along that path; and make farming easier by telling farmers each year when to plant and which crop.

## Status of the goal components

| Component | Status | Produced | To complete |
|---|---|---|---|
| A. Most suitable region wheat will shift to under climate change | Awaiting data | Reference → future climate difference computed per cell; the shift vector needs a trained model | `python3 -m fieldshift_data corridor --online (downloads the corridor grid from NASA and USDA)` |
| B. Split the path into parcels | Working | 30 pilot parcels + 0 migration-corridor parcels; 20 pilot points are non-cropland | `Corridor parcels need a trained model first: corridor --online.` |
| C. Economically most efficient rotation per parcel | Working | Profit optimisation and 3 strategies computed | `Fill config/economics_inputs.csv with sources, or run economics --online with FIELDSHIFT_NASS_KEY; for the climate→yield model: yield-model --online (needs a NASS key)` |
| D. Trained mathematical model | Insufficient training data | Cells with distinct climate 2 < 12; Cells with wheat 2 < 3; Cropland cells without wheat 2 < 3 | `corridor --online with at least 12 cells of different climate` |
| E. What to plant each year, and when | Working | Of 54 region-crop-years that need planting, 30 have a full window and 7 only a start or low confidence; crops without a rule: Dbl Crop WinWht/Soybeans, Triticale | `Source thresholds are in config/crop_calendar.json; validate with local soil temperature` |

## Planting windows (E)

For winter wheat the plan year is the harvest year; sowing is in the previous autumn.

| Region | Year | Crop | Start | End | Status | Basis |
|---|---|---|---|---|---|---|
| USKS01 | 2027 | Alfalfa | — | — | no_planting |  |
| USKS01 | 2027 | Corn | 2027-03-23 | 2027-07-27 | ok | NASA projection 2027 |
| USKS01 | 2027 | Dbl Crop WinWht/Soybeans | — | — | no_rule |  |
| USKS01 | 2027 | Sorghum | 2027-04-14 | 2027-08-01 | ok | NASA projection 2027 |
| USKS01 | 2027 | Soybeans | 2027-04-06 | 2027-07-17 | ok | NASA projection 2027 |
| USKS01 | 2027 | Winter Wheat | 2026-10-11 | 2026-10-25 | ok | NASA projection normal 2015–2024; 24 days (late December) from fewer than 80% of years |
| USKS01 | 2028 | Alfalfa | — | — | no_planting |  |
| USKS01 | 2028 | Corn | 2028-03-24 | 2028-07-26 | ok | NASA projection normal 2015–2024 |
| USKS01 | 2028 | Dbl Crop WinWht/Soybeans | — | — | no_rule |  |
| USKS01 | 2028 | Sorghum | 2028-04-22 | 2028-07-31 | ok | NASA projection normal 2015–2024 |
| USKS01 | 2028 | Soybeans | 2028-04-06 | 2028-07-16 | ok | NASA projection normal 2015–2024 |
| USKS01 | 2028 | Winter Wheat | 2027-10-11 | 2027-10-25 | ok | NASA projection normal 2015–2024; 24 days (late December) from fewer than 80% of years (actual year incomplete: 2027 August–December days missing (5 days)) |
| USOR03 | 2027 | Alfalfa | — | — | no_planting |  |
| USOR03 | 2027 | Fallow/Idle Cropland | — | — | no_planting |  |
| USOR03 | 2027 | Other Hay/Non Alfalfa | — | — | no_planting |  |
| USOR03 | 2027 | Peas | 2027-01-26 | — | low_confidence | NASA projection 2027 |
| USOR03 | 2027 | Spring Wheat | 2027-01-21 | — | low_confidence | NASA projection 2027 |
| USOR03 | 2027 | Triticale | — | — | no_rule |  |
| USOR03 | 2027 | Winter Wheat | 2026-10-06 | 2026-10-20 | ok | NASA projection normal 2015–2024; 24 days (late December) from fewer than 80% of years |
| USOR03 | 2028 | Alfalfa | — | — | no_planting |  |
| USOR03 | 2028 | Fallow/Idle Cropland | — | — | no_planting |  |
| USOR03 | 2028 | Other Hay/Non Alfalfa | — | — | no_planting |  |
| USOR03 | 2028 | Peas | 2028-02-07 | — | low_confidence | NASA projection normal 2015–2024 |
| USOR03 | 2028 | Spring Wheat | — | — | no_window | NASA projection normal 2015–2024 |
| USOR03 | 2028 | Triticale | — | — | no_rule |  |
| USOR03 | 2028 | Winter Wheat | 2027-10-06 | 2027-10-20 | ok | NASA projection normal 2015–2024; 24 days (late December) from fewer than 80% of years (actual year incomplete: 2027 August–December days missing (5 days)) |

**Check against the source record:** Oregon USOR03 winter wheat was sown on 15 October 2018. Computed window for harvest year 2019: 2018-10-06 – 2018-10-20 (NASA projection normal 2015–2024; 24 days (late December) from fewer than 80% of years (actual year incomplete: 2018 August–December days missing (4 days))).

## Parcel strategies (C)

30 parcels; 20 points were not counted as parcels because they are non-cropland.

| Region | Strategy | Example sequence | Total profit (USD/acre) | Status / missing |
|---|---|---|---|---|
| USKS01 | current | Soybeans → Soybeans → Soybeans → Soybeans → Sorghum → Soybeans | -184 | ok:  |
| USKS01 | most_profitable | Sorghum → Sorghum → Winter Wheat → Sorghum → Sorghum → Winter Wheat | 49 | ok:  |
| USKS01 | wheat_focused | Sorghum → Sorghum → Winter Wheat → Sorghum → Winter Wheat → Winter Wheat | -11 | ok:  |
| USOR03 | current | Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland | -91 | ok:  |
| USOR03 | most_profitable | Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat | 71 | ok:  |
| USOR03 | wheat_focused | Fallow/Idle Cropland → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Winter Wheat | -91 | ok:  |

### Price scenarios (±20% of source prices; sensitivity assumption)

| Region | Price factor | Typical most profitable sequence | Mean most profitable $/acre | Mean current $/acre |
|---|---:|---|---:|---:|
| USKS01 | 0.8 | Sorghum → Sorghum → Winter Wheat → Sorghum → Sorghum → Winter Wheat | -391 | -815 |
| USOR03 | 0.8 | Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat | -184 | -260 |
| USKS01 | 1.0 | Sorghum → Sorghum → Winter Wheat → Sorghum → Sorghum → Winter Wheat | 49 | -290 |
| USOR03 | 1.0 | Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat | 71 | -24 |
| USKS01 | 1.2 | Sorghum → Sorghum → Winter Wheat → Soybeans → Sorghum → Sorghum | 497 | 236 |
| USOR03 | 1.2 | Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat → Fallow/Idle Cropland → Winter Wheat | 328 | 211 |

All parcels and years: `parcel_plans.csv`, `parcel_strategies.csv`; for maps: `parcels.geojson`.

## P removal (soil nutrient balance constraint)

| Crop | kg P/ha/yr (median) | Systems | Range |
|---|---:|---:|---|
| Alfalfa | 27.0 | 6 | 10.7–37.2 |
| Barley | 26.5 | 4 | 25.7–31.2 |
| Canola | 3.1 | 2 | 2.7–3.5 |
| Corn | 31.5 | 27 | 8.7–70.8 |
| Sorghum | 17.0 | 1 | 17.0–17.0 |
| Soybeans | 18.8 | 22 | 3.1–27.0 |
| Spring Wheat | 30.5 | 3 | 13.0–30.7 |
| Winter Wheat | 12.0 | 16 | 1.0–38.1 |

## Limits of interpretation

- The current rotation is assumed to be the cyclic continuation of the 2018–2023 CDL sequence.
- Parcels in one region share the same county yield, price and cost; parcels differ only by their crop history.
- Rotation effects on yield enter only through sourced rotation_effects rows; currently wheat after wheat in Oregon (Maaz et al. 2017).
- Planting windows use air temperature as a proxy for soil temperature and rely on the NEX-GDDP ensemble mean.
- This tool supports decisions; it does not replace the judgement of the farmer or a local expert.

## Components A and D from the reference full run (added by the demo)

No corridor cache was found on this machine, so the suitability model was retrained on the packaged cell table of the team's full online run (`data/reference/corridor_cells_full_run.csv`: USDA CDL 2019–2023 wheat labels × NASA NEX-GDDP SSP2-4.5 cell climate). The status table above was written before this step.

- Spatial block cross-validation AUC: 0.595 (0.5 = random)
- Suitable zone (probability ≥ 0.5): 21 → 28 cells; gained 7, lost 0
- Zone centre shift: 114.8 km at 7° (0° north)
- Warning: the suitable zone touches the edge of the study box; the shift may be larger.
