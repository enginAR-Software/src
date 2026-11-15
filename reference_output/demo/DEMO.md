# FieldShift usage demo

Goal output: `goal_20261115T160645Z_313d0d22`

## 1. Status of the five goal components

- **A. Most suitable region wheat will shift to under climate change** — working: Suitable zone 21 → 28 cells; centre shifts 115 km at 7° (reference full run)
- **B. Split the path into parcels** — working: 30 pilot parcels + 0 migration-corridor parcels; 20 pilot points are non-cropland
- **C. Economically most efficient rotation per parcel** — working: Profit optimisation and 3 strategies computed
- **D. Trained mathematical model** — trained: Logistic model, spatial block validation AUC=0.595 (reference full run)
- **E. What to plant each year, and when** — working: Of 54 region-crop-years that need planting, 30 have a full window and 7 only a start or low confidence; crops without a rule: Dbl Crop WinWht/Soybeans, Triticale

## 2. Example: what one farmer is told

### Kansas pilot (near Manhattan, KS), parcel `USKS01:r1:c2`

Recommended 6-year rotation: **sorghum → sorghum → winter wheat → sorghum → sorghum → winter wheat**, total profit 49 $/acre (current rotation: -184 $/acre).

| Year | Plant | Planting window |
|---|---|---|
| 2027 | sorghum | 2027-04-14 – 2027-08-01 |
| 2028 | sorghum | 2028-04-22 – 2028-07-31 |
| 2029 | winter wheat | 2028-10-11 – 2028-10-25 |
| 2030 | sorghum | 2030-04-22 – 2030-07-31 |
| 2031 | sorghum | 2031-04-22 – 2031-07-31 |
| 2032 | winter wheat | 2031-10-11 – 2031-10-25 |

### Oregon pilot (near Pendleton, OR), parcel `USOR03:r0:c1`

Recommended 6-year rotation: **fallow → winter wheat → fallow → winter wheat → fallow → winter wheat**, total profit 71 $/acre (current rotation: -91 $/acre).

| Year | Plant | Planting window |
|---|---|---|
| 2027 | fallow | no planting |
| 2028 | winter wheat | 2027-10-06 – 2027-10-20 |
| 2029 | fallow | no planting |
| 2030 | winter wheat | 2029-10-06 – 2029-10-20 |
| 2031 | fallow | no planting |
| 2032 | winter wheat | 2031-10-06 – 2031-10-20 |

## 3. Date query

On 2027-04-20, 9 parcels are in their planting window for: sorghum.
Command: `python3 -m fieldshift_data goal-view goal_20261115T160645Z_313d0d22 --date 2027-04-20`

## 4. Where wheat is moving

Source: the cell table of the team's full online corridor run (USDA CDL 2019–2023 labels × NASA NEX-GDDP features), packaged in `data/reference/`; the model is retrained on it here.
Suitable wheat zone: 21 → 28 one-degree cells; its centre moves 115 km at 7° (0° = north) between 2015–2024 and 2040–2049. Spatial cross-validation AUC 0.595.

## 5. Files to open

- `outputs/app_20261115T160721Z_bf3a496b/FieldShift_App.html` — interactive map, parcel plans, date query, farmer priorities
- `outputs/goal_20261115T160645Z_313d0d22/DASHBOARD.html` — goal dashboard
- `outputs/goal_20261115T160645Z_313d0d22/GOAL_REPORT.md` — full report with sources and limitations

