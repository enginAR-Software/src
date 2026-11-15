"""Interactive FieldShift interface: a single file that opens in a browser and works without internet.

Data come from the goal output and the packaged configuration; no number is invented.
The rotation search runs in the browser with app_optimizer.js (same rules as economics.py).
"""

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import fmean
from uuid import uuid4

from . import satellite, yieldmodel, economics, geo, planting

ASSETS = Path(__file__).resolve().parent / "assets"
STATUS_LABELS = {"working": "Working", "awaiting_inputs": "Awaiting inputs", "awaiting_data": "Awaiting data",
             "trained": "Trained", "insufficient_training_data": "Insufficient training data"}


def read_csv(path):
    with Path(path).open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def collect(workspace, goal_dir, econ_config_path, inputs_path, calendar_path):
    workspace, goal_dir = Path(workspace).resolve(), Path(goal_dir)
    report = json.loads((goal_dir / "goal.json").read_text(encoding="utf-8"))
    econ = json.loads(Path(econ_config_path).read_text(encoding="utf-8"))
    economics.validate_config(econ)
    calendar = planting.load_calendar(calendar_path)
    manual = economics.load_inputs(inputs_path)
    nass, _, _ = economics.nass_inputs(workspace, econ, False)
    inputs = economics.merge_inputs(nass, manual)
    p_removal = economics.p_removal_by_crop(workspace)

    plans = read_csv(goal_dir / "parcel_plans.csv")
    current = {}
    for row in plans:
        if row["strategy"] == "current":
            current.setdefault(row["parcel_id"], []).append((int(row["plan_year"]), row["crop"]))
    features = json.loads((goal_dir / "parcels.geojson").read_text(encoding="utf-8"))["features"]
    parcels = []
    for f in features:
        p = f["properties"]
        observed_classes = p["observed_sequence"].split(" → ")
        observed = [economics.CDL_TO_CROP.get(c, c) for c in observed_classes]
        parcels.append({"id": p["parcel_id"], "region": p["region"], "site": p.get("site", p["region"]), "kind": p.get("kind", "pilot"),
                        "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
                        "observed": observed,
                        "observed_years": [int(str(p.get("observed_years", "2018")).split("-")[0]) + i for i in range(len(observed))]
                        if p.get("kind") == "corridor" else [2018 + i for i in range(len(observed))],
                        "previous": observed[-1], "initial_run": economics.years_without_fallow(observed),
                        "current": [c for _, c in sorted(current.get(p["parcel_id"], []))]})

    windows = {}
    for w in read_csv(goal_dir / "planting_windows.csv"):
        windows.setdefault(w["region"], {}).setdefault(w["crop"], {})[int(w["plan_year"])] = {
            "start": w["start"] or None, "end": w["end"] or None, "status": w["status"], "basis": w["basis"] or None,
            "detail": w["detail"] or None}

    regions = {}
    for region in sorted({p["region"] for p in parcels}):
        ps = [p for p in parcels if p["region"] == region]
        crop_inputs = {}
        for (r, crop), entry in inputs.items():
            if r == region:
                crop_inputs[crop] = {k: entry.get(k) for k in ("yield", "price", "cost", "unit", "yield_source", "price_source", "cost_source")}
        pilot = region.startswith("US")
        regions[region] = {"name": {"USKS01": "Kansas pilot (Riley County, near Manhattan)", "USOR03": "Oregon pilot (Umatilla County, near Pendleton)"}.get(
                               region, geo.NAMES.get(region, region) + " (migration corridor)"),
                           "short": {"USKS01": "Kansas", "USOR03": "Oregon"}.get(region, geo.NAMES.get(region, region)), "pilot": pilot,
                           "lon": fmean(p["lon"] for p in ps), "lat": fmean(p["lat"] for p in ps),
                           "allowed": econ["allowed_crops"].get(region, []), "inputs": crop_inputs,
                           "fallow_rule": econ.get("fallow_requirement", {}).get(region)}

    corridor_dir = workspace / "outputs" / report["corridor_output"]
    cells = []
    if (corridor_dir / "corridor_cells.csv").is_file():
        for c in read_csv(corridor_dir / "corridor_cells.csv"):
            if c.get("suitability_baseline") and c.get("longitude"):
                cells.append({"id": c["cell_id"], "lon": float(c["longitude"]), "lat": float(c["latitude"]),
                              "sb": float(c["suitability_baseline"]), "sf": float(c["suitability_future"]),
                              "wheat_points": int(c["wheat_points"] or 0), "cropland_points": int(c["cropland_points"] or 0)})
    climate, shift_rows = [], []
    dash_dir = goal_dir / "dashboard_data"
    if (dash_dir / "climate_shift.csv").is_file():
        climate = read_csv(dash_dir / "climate_shift.csv")
    if (dash_dir / "planting_shift.csv").is_file():
        shift_rows = read_csv(dash_dir / "planting_shift.csv")

    sources = [{"label": "Planting thresholds", "text": "; ".join(f"{crop}: {', '.join(v for v in rule['sources'].values())}"
                                                       for crop, rule in calendar["crops"].items() if rule["type"] != "none")},
               {"label": "Phosphorus fertilizer price", "text": econ.get("p_fertilizer_price_source", "")},
               {"label": "Fallow cost", "text": econ.get("fallow_cost_source", "")},
               {"label": "P removal", "text": "P-FLUX (Williams et al. 2021), median of system means per crop. https://doi.org/10.15482/USDA.ADC/1523365"},
               {"label": "Parcels", "text": "USDA NASS Cropland Data Layer 2018–2023, 30 m (CroplandCROS)."},
               {"label": "Climate", "text": "NASA POWER, NEX-GDDP-CMIP6 ensemble, SSP2-4.5 daily projection."}]
    for rule in econ.get("fallow_requirement", {}).values():
        sources.append({"label": "Fallow rule", "text": rule["source"]})
    for note in econ.get("input_notes", []):
        sources.append({"label": "Note", "text": note})

    sat_output, sat = satellite.latest(workspace)
    satellite_data = {pid: {"m": {k: v["metrics"].get(k) for k in ("year", "status", "peak_ndvi", "peak_date", "green_up", "senescence",
                                                                  "bare_soil_days", "cdl_crop", "phenology_check")},
                            "s": v["series"]} for pid, v in sat.items()}
    yield_output, _, yield_rows = yieldmodel.latest_multipliers(workspace)
    yields = {}
    for r in yield_rows:
        if not r.get("cell_id") or not r.get("crop"):
            continue
        yields.setdefault(r["cell_id"], {})[r["crop"]] = {
            "mult": float(r["yield_multiplier"]) if r.get("yield_multiplier") not in (None, "", "None") else None,
            "status": r.get("model_status"), "extrap": r.get("extrapolation") == "1"}
    future = {}
    if (goal_dir / "parcel_strategies.csv").is_file():
        for r in read_csv(goal_dir / "parcel_strategies.csv"):
            if r["strategy"] == "most_profitable_2040" and r["sequence"]:
                future[r["parcel_id"]] = {"sequence": r["sequence"].split(" → "), "total": float(r["total_profit_usd_per_acre"]),
                                          "note": r["missing_inputs"]}
    if sat_output:
        sources.append({"label": "Satellite (NDVI)", "text": f"ORNL DAAC MODIS Web Service, MOD13Q1 v061 250 m 16-day NDVI (doi:10.5067/MODIS/MOD13Q1.061); output {sat_output}."})
    if yield_output:
        sources.append({"label": "Climate-to-yield", "text": f"USDA NASS Quick Stats county yields 2014–2023 × NASA NEX-GDDP cell climate; ridge regression, spatial block validation; output {yield_output}."})

    return {
        "satellite": satellite_data, "satellite_output": sat_output, "yields": yields, "yield_output": yield_output, "future": future,
        "goal": report["goal"], "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "components": [{"key": k, "component": report["components"][k], "status": report["status"][k]["status"],
                        "status_label": STATUS_LABELS.get(report["status"][k]["status"], report["status"][k]["status"]),
                        "produced": report["status"][k]["produced"], "next": report["status"][k]["next"]} for k in "ABCDE"],
        "plan_years": report["plan_years"], "regions": regions, "parcels": parcels, "windows": windows,
        "calendar": {crop: {"type": rule["type"], "season_days": rule.get("season_days")} for crop, rule in calendar["crops"].items()},
        "p_removal": p_removal,
        "params": {"max_consecutive": econ["max_consecutive_same_crop"], "min_wheat": econ.get("min_wheat_seasons", 0),
                   "wheat_share": econ.get("wheat_focused_min_share", 0.5), "p_price": econ.get("p_fertilizer_price_usd_per_kg_p"),
                   "fallow_cost": econ.get("fallow_cost_usd_per_acre"), "acres_per_ha": economics.ACRES_PER_HA,
                   "rotation_effects": econ.get("rotation_effects", [])},
        "cells": cells, "corridor": report["corridor"], "climate": climate, "planting_shift": shift_rows,
        "sources": sources, "limitations": report.get("limitations", []),
    }


def render(data):
    template = (Path(__file__).resolve().parent / "app_template.html").read_text(encoding="utf-8")
    states = (ASSETS / "us_states.json").read_text(encoding="utf-8")
    safe = lambda text: text.replace("</", "<\\/")
    return (template.replace("/*__D3__*/", (ASSETS / "d3.min.js").read_text(encoding="utf-8"))
            .replace("/*__LEAFLET__*/", (ASSETS / "leaflet.js").read_text(encoding="utf-8"))
            .replace("/*__LEAFLET_CSS__*/", (ASSETS / "leaflet.css").read_text(encoding="utf-8"))
            .replace("/*__OPT__*/", (Path(__file__).resolve().parent / "app_optimizer.js").read_text(encoding="utf-8"))
            .replace("/*__DATA__*/null", safe(json.dumps(data, ensure_ascii=False)))
            .replace("/*__STATES__*/null", safe(states)))


def build(workspace, goal_dir, econ_config_path, inputs_path, calendar_path):
    data = collect(workspace, goal_dir, econ_config_path, inputs_path, calendar_path)
    output = Path(workspace).resolve() / "outputs" / ("app_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    (output / "FieldShift_App.html").write_text(render(data), encoding="utf-8")
    (output / "app_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return output / "FieldShift_App.html", data
