# Interactive interface

```bash
python3 -m fieldshift_data app --open     # or: python3 -m fieldshift_data demo --open
```

This builds one self-contained file, `outputs/app_*/FieldShift_App.html`, and opens it in a browser.

- It needs no server and no installation.
- Without internet, the map falls back to offline state boundaries; with internet it uses the USGS base map.
- No number on the page is invented: it comes from the goal output and the sourced configuration.

## Map (GIS)

- Leaflet map. Display projection is EPSG:3857; all data are in EPSG:4326.
- **Base layers:** USGS National Map topographic, imagery, imagery with labels, or offline boundaries only.
- **Overlays:**
  - US Census state boundaries;
  - wheat-suitability cells for 2015–2024, 2040–2049, or the change;
  - the shift arrow of the suitable-zone centre;
  - pilot sites;
  - parcels (CDL 30 m points; the real 30 m square appears when you zoom in).
- **Views:** USA, Migration corridor, Kansas parcels, Oregon parcels, Corridor parcels.
- **Downloads:** parcels with their plans, and corridor cells, both as GeoJSON for use in QGIS or ArcGIS.

## Tabs

| Tab | What it shows |
|---|---|
| **Parcel plan** | The satellite crop history, then three strategies: recommended (most profitable), wheat-focused, and current. For every year it lists the crop, the planting window, the profit and the P removal, followed by "Why this plan?". When the data exist, it also shows the planting calendar shift, the 2040s yield change and the MODIS NDVI curve. |
| **What to plant on a date?** | For any date: which parcels are in their planting window, before it, or past it. |
| **Farmer priorities** | Choose crops, the minimum number of wheat years, the maximum number of years in a row for one crop, the price scenario (−20% / source / +20%) and the Oregon fallow rule. All plans are recomputed in the browser by `app_optimizer.js`, which uses the same rules as `economics.py` (tested against it). |
| **Migration** | Shift of the suitable zone (km and bearing), suitable cells today vs the 2040s, model AUC, and the climate change for each cell. |
| **Sources** | Each economic input with its source, and every other source and note. |

Crop colours, legends and labels are in English. Dates are written as "Apr 14, 2027".
