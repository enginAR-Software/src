# FieldShift methods

FieldShift links one goal statement ([Preparation.md](../Preparation.md)) to five components, A–E. This document describes how each component is computed, which data it uses and where its limits are. Every threshold and economic input has its source written in `config/`.

## A + D. Migration region and suitability model (`suitability.py`, `corridor` command)

**Study area.** The Great Plains wheat belt from Kansas to North Dakota (36–49°N, 95–102°W). It is split into 91 one-degree cells, with 3 × 3 sample points per cell (819 points, spacing 0.1°). Settings: `config/corridor.json`.

**Labels.** For each point, the USDA Cropland Data Layer class is read for 2019–2023 through the CroplandCROS service. A cropland point that grew wheat in at least one year is labelled 1; a cropland point without wheat is labelled 0.

**Features.** For each cell centre, daily NASA POWER NEX-GDDP-CMIP6 projections are downloaded (SSP2-4.5, ensemble mean) for a reference period (2015–2024) and a future period (2040–2049). Five mean-based features are computed:

- annual mean temperature;
- annual growing degree days (base 0 °C);
- June–July mean daily maximum temperature;
- annual precipitation;
- October–June precipitation.

Each feature needs at least 90% of its days. Threshold-exceedance counts are deliberately not used, because ensemble-mean days smooth out extremes.

**Model.** Logistic regression with L2 regularisation (λ = 0.1), implemented in the standard library.

**Validation.** Spatial block cross-validation with 2 × 2-cell blocks: each block is the test fold once, and neighbouring cells never leak between training and testing. Two scores are reported:

- **AUC**;
- **Brier score**, compared with a model that only knows the prevalence.

**Projection.** The trained model is applied to the 2040–2049 features of the same scenario. Cells with probability ≥ 0.5 form the *suitable zone*. The output reports the shift of the zone's centre (distance and bearing), the cells gained and lost, and a warning if the zone touches the edge of the study box.

**Result (team's full run, 15 Nov 2026).**
- Suitable zone: 21 → 28 cells, 7 gained, 0 lost.
- The zone centre moves 114.8 km at a bearing of 7°.
- AUC 0.595; Brier 0.2275, against 0.2387 for prevalence only.

The cell table of that run is packaged as `data/reference/corridor_cells_full_run.csv`. The `demo` command retrains the model on it when no corridor cache is present.

## B. Parcels (`goal.py`)

- **Pilot parcels.** Two NAPESHM long-term research sites: USKS01 (Riley County, near Manhattan, KS) and USOR03 (Umatilla County, near Pendleton, OR). On each, a 5 × 5 grid of CDL points is read for 2018–2023. Points that were cropland in every year become parcels (30 of 50).
- **Corridor parcels.** CDL points in cells that are suitable in 2040–2049 and were cropland in every year 2019–2023. Each parcel's economic region is its state (US Census boundaries). Its planting calendar uses its own cell's NASA climate.

A parcel is a 30 m CDL pixel, not a surveyed field boundary.

## C. Economic rotation model (`economics.py`)

For each parcel and plan period 2027–2032, every valid 6-year crop sequence is enumerated. The sequence with the highest total profit wins.

```
profit(year) = yield × rotation multiplier(previous → crop) × price × price scenario
               − production cost − P removal (kg/ha ÷ 2.471) × P fertilizer price
```

The last term charges the cost of replacing the phosphorus each crop removes. P removal comes from P-FLUX: the median across systems of each system's mean.

**Constraints**
- the same crop at most 2 years in a row;
- at least 1 wheat season;
- in Oregon, at most 2 years without fallow (USDA ARS rainfall zones; Pendleton ≈ 406 mm);
- a summer crop must be harvested before the latest sowing date of a following winter wheat (from component E).

**Rotation effect.** In Oregon, winter wheat after wheat gets a ×0.618 yield multiplier (Maaz et al. 2017, Table 4).

**Strategies**
- `current`: cyclic continuation of the CDL history;
- `most_profitable`;
- `wheat_focused`: wheat in at least half of the years;
- `most_profitable_2040`: corridor parcels only, with 2040s yields.

**Inputs** (`config/economics_inputs.csv`). Every value must have a source, or it is rejected.
- Kansas: K-State KFMA, 2020–2024 averages.
- Oregon wheat: USDA NASS Oregon bulletin and OSU budget AEB0064.
- Fallow cost: OSU AEB0045.
- P fertilizer price: USDA AMS via farmdoc daily, 3.91 $/kg P.
- Other states: USDA ERS 2027 cost forecasts; yields and prices from NASS Quick Stats with a free key.

Manual sourced values override NASS values.

**Price scenarios.** Source prices × 0.8, 1.0 and 1.2 (a sensitivity assumption, not a forecast).

**Climate-to-yield model** (`yieldmodel.py`, `yield-model` command)
1. NASS county yields (2014–2023, at least 3 years per county) are assigned to corridor cells through county centroids.
2. A ridge regression is fitted on the cell climate features plus squared temperature terms.
3. The model is validated with spatial block cross-validation.
4. For crops with R² ≥ 0.2, the 2040s yield multiplier = prediction(future) / prediction(reference), clipped to [0.5, 1.5].
5. Cells whose future climate lies outside the training range are excluded.

## E. When to plant (`planting.py`, `config/crop_calendar.json`)

For every crop and plan year, the window comes from that year's NASA daily projection. If that year is incomplete, the nearest 10-year normal is used.

| Crop | Rule |
|---|---|
| Corn | 3-day mean ≥ 10 °C, staying above it for 7 days; season 110 days (assumption) |
| Soybeans | ≥ 12.8 °C; season 120 days (assumption) |
| Sorghum | ≥ 15.6 °C; season 105 days (OSU EM 8794) |
| Spring wheat | ≥ 1.7 °C, search from 10 January |
| Peas | ≥ 4.4 °C, search from 10 January |
| Winter wheat | latest sowing = last day with ≥ 389 °C·days (base 0 °C) accumulated by 31 December; window opens 14 days earlier; the plan year is the harvest year |

- **Season end:** for spring crops, the autumn day when the 7-day mean drops below the base temperature, minus the season length.
- **Low confidence:** a threshold crossed before 1 March is flagged `low_confidence`.
- **Late-December gaps:** up to 3 missing days in NEX-GDDP are tolerated and disclosed.
- **Check:** the computed 2019 window at Oregon USOR03 is compared with the recorded sowing on 15 October 2018.

## Satellite indicator (`satellite.py`, `satellite` command)

MODIS MOD13Q1 v061 NDVI (250 m, 16-day) is read from the ORNL DAAC MODIS Web Service, at most 10 dates per request, for each parcel. The indicator reports:
- peak NDVI and date;
- green-up and senescence (half-amplitude threshold);
- bare-soil days (NDVI < 0.25);
- whether the peak month matches the typical peak months of the crop CDL reports (`config/phenology.json`: Wardlow et al. 2007; USDA Agricultural Handbook 628).

## Limitations

- The suitability model is weak (AUC 0.595). It mainly learned "drier/west means more wheat" and that warmth helps. It cannot see heat losses in the south, because the training data contain no hotter climates (extrapolation).
- The suitable zone touches the northern edge of the study box, so the real shift is probably larger. Widening the box and adding Canada (AAFC Annual Crop Inventory) are the next steps.
- Only one emission scenario (SSP2-4.5) and the ensemble mean are used; model spread is not shown.
- Planting windows use air temperature as a proxy for soil temperature.
- Parcels in one region share the same yields, prices and costs; they differ only by crop history.
- Outside Kansas, costs are US averages.
- The tool supports decisions; it does not replace the judgement of the farmer or a local expert.
