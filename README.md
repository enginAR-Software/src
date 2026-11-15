# FieldShift

**Following wheat's climate migration, parcel by parcel.**
NASA Space Apps Challenge 2026 · Challenge: *Field Shift: Adapting Farms with NASA Data*

FieldShift estimates where wheat-suitable land in the North American Great Plains will move as the climate warms. It then turns that estimate into a year-by-year plan for individual fields: **what to plant, when to plant it, and why**.

Version 1.0.0 · Python 3.10+ standard library only · works offline · MIT License

---

## 1. Run the demo (one command, no internet, no installation)

```bash
python3 -m fieldshift_data demo --open
```

The demo:

1. runs all five goal components on the packaged data;
2. builds the goal dashboard;
3. builds the interactive map;
4. opens the map in your browser;
5. prints a summary that is also saved as `DEMO.md`.

The summary contains:

- the status of each goal component;
- the recommended 6-year rotation with planting dates for one Kansas parcel and one Oregon parcel;
- a "what do I plant on this date?" query;
- the migration result.

Example output, abridged:

```
A. Most suitable region wheat will shift to under climate change — working: Suitable zone 21 → 28 cells; centre shifts 115 km at 7°
D. Trained mathematical model — trained: Logistic model, spatial block validation AUC=0.595

Kansas pilot (near Manhattan, KS), parcel USKS01:r1:c2
Recommended 6-year rotation: sorghum → sorghum → winter wheat → sorghum → sorghum → winter wheat,
total profit 49 $/acre (current rotation: -184 $/acre).
| 2027 | sorghum      | 2027-04-14 – 2027-08-01 |
| 2029 | winter wheat | 2028-10-11 – 2028-10-25 |

Oregon pilot (near Pendleton, OR): fallow → winter wheat → fallow → winter wheat → ...
(the model independently finds the region's real wheat–fallow rotation)
```

Then open the files listed at the end of the demo output:

| File | What it is |
|---|---|
| `outputs/app_*/FieldShift_App.html` | Interactive map: wheat-suitability cells today and in the 2040s, the shift of the suitable zone, parcels, the yearly plan for each parcel, a date query, farmer priorities (crops, rules, price scenario) and all sources. |
| `outputs/goal_*/DASHBOARD.html` | Goal dashboard: planting calendar shift, strategy comparison, parcel plans, migration map. |
| `outputs/goal_*/GOAL_REPORT.md` | Full report with every number, its source and the limits of interpretation. |

To test the code itself:

```bash
python3 -m unittest discover -s tests      # 114 tests
```

## 2. What FieldShift does: the five goal components

The project goal ([Preparation.md](Preparation.md)) is split into five components. Every report and the interface show the status of each one.

| | Goal component | How FieldShift does it | Main data |
|---|---|---|---|
| **A** | Most suitable region wheat will migrate to | Wheat suitability per 1° cell for today's climate and for the 2040s; shift of the suitable zone | USDA Cropland Data Layer + NASA NEX-GDDP-CMIP6 |
| **B** | Split the path into parcels | Parcels from 30 m CDL points that were cropland every year; pilot sites and the migration corridor | USDA CDL, US Census boundaries |
| **C** | Economically most efficient rotation per parcel | Exhaustive search over every valid 6-year rotation, maximising profit including the cost of replacing soil phosphorus | K-State KFMA, USDA NASS/ERS, OSU, P-FLUX |
| **D** | A trained mathematical model | Logistic suitability model and climate-to-yield ridge model, both with spatial block cross-validation | as A and C |
| **E** | Tell farmers when to plant and what | Planting window for every crop and year from projected daily temperature and published thresholds | NASA NEX-GDDP-CMIP6, extension publications |

Methods in detail: [docs/METHODS.md](docs/METHODS.md).

## 3. Results

| Result | Value |
|---|---|
| Warming 2015–2024 → 2040–2049 (SSP2-4.5) | +1.0 to +1.4 °C annual mean; up to +1.6 °C June–July maximum; strongest in the north |
| Wheat-suitable cells (probability ≥ 0.5) | 21 → 28, of 91 |
| Shift of the suitable-zone centre | about 115 km, bearing 7° (north) |
| Suitability model, spatial block cross-validation | AUC 0.595: weak, reported honestly |
| Planting-window shift at the pilot sites | Kansas corn 6 days earlier; Oregon peas 11 days earlier; winter-wheat sowing 4–5 days later |
| Oregon pilot | The optimiser reproduces the real wheat–fallow rotation of the region |
| Kansas pilot | The recommended sorghum–winter-wheat rotation is unchanged under a 20% price drop |

Two caveats apply to these results:

- The suitable zone touches the northern edge of the study area, so the real shift is probably larger.
- The model does not capture heat losses in the south.

See [docs/METHODS.md § Limitations](docs/METHODS.md#limitations).

## 4. NASA and partner data

| Data | Provider | Used for |
|---|---|---|
| NEX-GDDP-CMIP6 daily climate projections (SSP2-4.5), via **NASA POWER** | NASA | Climate features of the suitability model (A, D), planting windows (E), crop-sequence feasibility (C), yield-model predictors (C, D) |
| MERRA-2 historical daily weather, via **NASA POWER** | NASA | Matching recorded field operations with observed weather (pilot analysis) |
| **MODIS** MOD13Q1 v061 NDVI, via ORNL DAAC | NASA | Satellite check of crop labels; green-up, peak and bare-soil days per parcel |
| Cropland Data Layer (30 m), via CroplandCROS | USDA NASS (classified from Landsat and Sentinel-2 imagery) | Where wheat grows (labels), parcels, crop histories |
| Quick Stats | USDA NASS | State and county yields and prices |
| Cost-of-production forecasts | USDA ERS | Costs outside Kansas |
| KFMA enterprise data | Kansas State University | Kansas yields, prices, costs |
| Enterprise budgets AEB0064, AEB0045 | Oregon State University | Oregon wheat and fallow costs |
| P-FLUX (Williams et al. 2021) | USDA ARS / LTAR | Phosphorus removed by each crop |
| NAPESHM (Soil Health Institute 2024, CC BY 4.0) | Soil Health Institute | Pilot sites and field management records |
| State and county boundaries (us-atlas) | US Census | State lookup, county centroids, map |
| National Map tiles | USGS | Base map (display only) |

The full list with DOIs, URLs and licences is in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## 5. Full workflow with live data

The demo uses the packaged data, plus the cell table of the team's full corridor run in `data/reference/`. To reproduce everything from the original sources:

```bash
python3 -m fieldshift_data corridor --online          # A + D: download the 91-cell corridor (NASA POWER + USDA CDL; 1–2 h, cached)
export FIELDSHIFT_NASS_KEY=your_key                    # free key: https://quickstats.nass.usda.gov/api
python3 -m fieldshift_data economics --online         # C: NASS state yields and prices
python3 -m fieldshift_data yield-model --online       # C + D: county yield ~ climate model, 2040s yield multipliers
python3 -m fieldshift_data goal --offline             # A–E together → GOAL_REPORT.md, DASHBOARD.html
python3 -m fieldshift_data satellite --online         # MODIS NDVI for every parcel (no key needed)
python3 -m fieldshift_data app --open                 # interactive map
python3 -m fieldshift_data goal-view outputs/goal_<id> --date 2027-04-20   # what to plant on a date
```

- Every download is stored once with a SHA-256 receipt.
- `--offline` uses only the verified cache.
- The NASS key is never written to disk.

All commands: `python3 -m fieldshift_data --help`. Interface guide: [docs/INTERFACE.md](docs/INTERFACE.md). NASS key: [docs/NASS_KEY.md](docs/NASS_KEY.md).

## 6. Project layout

```
fieldshift_data/      Python package (standard library only)
  goal.py             components A–E in one run
  suitability.py      A + D: wheat suitability model and migration corridor
  economics.py        C: rotation optimiser, NASS inputs
  planting.py         E: planting windows
  yieldmodel.py       C + D: climate-to-yield model
  satellite.py        MODIS NDVI indicator
  app.py, app_template.html, app_optimizer.js   interactive interface
  dashboard.py        goal dashboard
  demo.py             one-command demo
  assets/             Leaflet, d3, US state boundaries, county centroids (with licences)
config/               sourced inputs: crop calendar, economics, corridor, phenology
data/raw/             packaged source data and caches (SHA-256 receipts)
data/reference/       cell table of the team's full corridor run
docs/                 METHODS, DATA_SOURCES, INTERFACE, NASS_KEY (docs/tr: Turkish documents)
reference_output/     reference outputs of earlier runs
tests/                114 automated tests
```

## 7. Principles

- **No invented numbers.** Every yield, price, cost and threshold has a source written next to it. A missing value is reported as missing and never filled in.
- **Honest validation.** Models are tested on regions they have not seen (spatial block cross-validation), and weak results are reported as weak.
- **Decision support, not a prescription.** Local soil temperature, field conditions and the farmer's judgement come first.

## 8. Use of artificial intelligence

This software, its documentation, charts and texts were developed with the help of **Claude (Anthropic)**, an AI assistant. It was used for writing and testing code, checking sources, running analyses and drafting and translating texts.

The team defined the goal, chose the approach, downloaded the data, ran the software and reviewed the results. All input values come from the cited public datasets; no data values were generated by AI. No NASA logos or mission identifiers were generated or modified.

## 9. Licence

Code: MIT ([LICENSE](LICENSE)). Data keep their own licences, listed in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) and `fieldshift_data/assets/LICENSES.txt`.
# src
