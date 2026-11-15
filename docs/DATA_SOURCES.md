# Data sources and attribution

Sources were checked on 15 November 2026. Original numeric files are kept unchanged in `data/raw/` with SHA-256 receipts. Derived tables and summaries are produced by FieldShift and do not imply endorsement by the data providers.

## NASA

| Dataset | Use | Access |
|---|---|---|
| **NEX-GDDP-CMIP6** daily projections (SSP2-4.5, ensemble mean), through NASA POWER | Climate features (A, D), planting windows (E), feasibility (C), yield-model predictors | https://power.larc.nasa.gov/docs/services/api/projection/ — no key |
| **MERRA-2** historical daily weather, through NASA POWER | Matching recorded field operations with weather (pilot analysis) | https://power.larc.nasa.gov/docs/services/api/temporal/daily/ — no key |
| **MODIS MOD13Q1 v061** NDVI, 250 m, 16-day (Didan 2021, doi:10.5067/MODIS/MOD13Q1.061), through the ORNL DAAC MODIS Web Service | Satellite indicator: greenness curve, bare-soil days, CDL check | https://modis.ornl.gov/rst/api/v1/ — no key |

NASA POWER attribution and terms: https://power.larc.nasa.gov/. Projection scenarios are never relabelled as observations.

## USDA and other agencies

| Dataset | Use | Access / licence |
|---|---|---|
| **Cropland Data Layer** (USDA NASS, 30 m, 2018–2023), via CroplandCROS. Classified from Landsat and Sentinel-2 imagery among other inputs | Wheat labels, parcels, crop histories | https://pdi.scinet.usda.gov/image/rest/services/CDL_WM/ImageServer — public domain |
| **NASS Quick Stats** | State yields and prices; county yields 2014–2023 | https://quickstats.nass.usda.gov/api — free key |
| **USDA ERS** cost-of-production forecasts 2026F–2027F | Costs outside Kansas | https://www.ers.usda.gov/media/4923/cost-of-production-forecasts-for-major-us-field-crops-2026f-2027f.csv |
| **USDA NASS Oregon Annual Statistical Bulletin 2024** | Oregon winter-wheat yield and price 2019–2023 | https://data.nass.usda.gov/Statistics_by_State/Oregon/Publications/Annual_Statistical_Bulletin/2024/OR_ANN_2024.pdf |
| **P-FLUX**: Williams et al. (2021), *LTAR Phosphorus Budget Summary*, Ag Data Commons | Phosphorus removed by each crop | https://doi.org/10.15482/USDA.ADC/1523365 — US public domain |
| **NAPESHM**: Soil Health Institute (2024), *North American Project to Evaluate Soil Health Measurements Dataset*, Ag Data Commons | Pilot sites, management records | https://doi.org/10.15482/USDA.ADC/25632270 — CC BY 4.0 |
| **US Census** state and county boundaries (us-atlas v3) | State lookup, county centroids, map layer | public domain; us-atlas ISC licence |
| **USGS The National Map** tiles | Base map (display only) | https://www.usgs.gov/programs/national-geospatial-program/national-map |

## Economic inputs and agronomic rules

| Source | Value used |
|---|---|
| Kansas State University, KFMA enterprise data (Dikeman, *Crop Profitability*) | Kansas non-irrigated corn, soybean, sorghum, wheat yields, prices, total costs, 2020–2024 |
| Oregon State University Enterprise Budget AEB0064 (2021) | Oregon winter wheat after fallow, total cost 336 $/acre |
| Oregon State University Enterprise Budget AEB0045 (2014) | Fallow cost 45.50 $/acre |
| USDA AMS Illinois Production Cost Report, via farmdoc daily (Paulson et al., Aug 2026) | P fertilizer price 3.91 $/kg P (from DAP after its N value) |
| Maaz et al. (2017), *Frontiers in Environmental Science* 5:23, Table 4 | Wheat-after-wheat yield multiplier 0.618 (Oregon) |
| USDA ARS, CBARC Pendleton (Williams; Machado et al. 2007) | Fallow requirement by rainfall zone |
| SDSU Extension; Oregon State University EM 8794; NDSU Extension A1166; Virginia Tech SPES-730; Top Crop Manager | Planting temperature thresholds and winter-wheat GDD rule |
| Wardlow, Egbert & Kastens (2007), *Remote Sensing of Environment* 108:290–310; USDA Agricultural Handbook 628 | Typical NDVI peak months per crop |

Full citations with URLs are written next to each value in `config/economics.json`, `config/economics_inputs.csv`, `config/crop_calendar.json` and `config/phenology.json`.

## Software

| Software | Licence |
|---|---|
| Python 3 standard library | PSF |
| Leaflet 1.9.4 | BSD 2-Clause |
| d3 v7.9.2 | ISC |

See `fieldshift_data/assets/LICENSES.txt`. FieldShift's own code is MIT-licensed (`LICENSE`).

## Team reference data

`data/reference/corridor_cells_full_run.csv` holds the 91-cell table produced by the team's full online `corridor` run on 15 November 2026. Each row contains:
- the CDL point counts with and without wheat;
- the NASA reference and future features;
- the model suitability.

It lets the demo reproduce components A and D without the 1–2 hour download.
