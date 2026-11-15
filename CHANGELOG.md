# Changelog

## 1.0.0 (15 November 2026): NASA Space Apps submission
- The whole package is now in English: command-line messages, reports, the interactive interface, the dashboard, configuration notes, documentation and status codes (for example `most_profitable`, `wheat_focused`, `current`, `missing_data`). The Turkish documents are kept in `docs/tr/`.
- New `demo` command: one offline command runs components A–E, builds the dashboard and the interactive map, and prints a farmer-level summary (`DEMO.md`).
- `data/reference/corridor_cells_full_run.csv`: the cell table of the team's full corridor run, so the demo reproduces components A and D without the 1–2 hour download.
- Dates in the interface are written as "Apr 14, 2027".

## 0.9.x
- Corridor parcels.
- Climate-to-yield model (`yield-model`).
- Oregon wheat-after-wheat effect and ±20% price scenarios.
- MODIS NDVI indicator (`satellite`).
- 0.9.1: fix for an empty yield-model output.

## 0.8.0
- Interactive interface (`app`) with a Leaflet/USGS GIS map.

## 0.7.x
- Goal components A–E (`goal`).
- Official economic inputs.
- Goal dashboard.
