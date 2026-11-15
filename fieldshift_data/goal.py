"""Joins the five components of the project goal (Preparation.md) into one output.

A  Most suitable region wheat will shift to under climate change   → suitability.py (corridor)
B  Split the regions along the path into parcels                  → CDL points (parcels)
C  Economically most efficient rotation per parcel                → economics.py
D  Trained mathematical model                                     → suitability.py (training + spatial validation)
E  Tell the farmer what to plant each year, and when              → planting.py

Output contract: for each parcel × strategy × plan year: crop, planting window, expected profit,
P removal, confidence and missing inputs. No missing value is ever filled in; it stays empty and the reason is written.
"""

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

from . import climate, economics, geo, planting, suitability, yieldmodel
from .tables import digest, write_csv, write_json

GOAL_TEXT = ("Using a range of data, estimate the most suitable region that North American wheat will migrate to "
             "under climate change; train a mathematical model that computes the economically most efficient crop rotation "
             "for the regions split into parcels along that path; and make farming easier by telling farmers each year "
             "when to plant and which crop.")
COMPONENTS = {
    "A": "Most suitable region wheat will shift to under climate change",
    "B": "Split the path into parcels",
    "C": "Economically most efficient rotation per parcel",
    "D": "Trained mathematical model",
    "E": "What to plant each year, and when",
}
OBSERVED_FIRST_YEAR = 2018


def parcels_from_observations(observations, plan_start, years):
    """B: every CDL point is a parcel candidate. Points that are cropland in every year become parcels."""
    by_point = {}
    for row in observations:
        by_point.setdefault(row["point_id"], []).append(row)
    parcels, excluded = [], []
    for point_id, rows in sorted(by_point.items()):
        rows.sort(key=lambda r: r["year"])
        classes = [r["class_name"] or None for r in rows]
        crops = [economics.CDL_TO_CROP.get(c) for c in classes]
        record = {"parcel_id": point_id, "region": rows[0]["sitecode"], "longitude": rows[0]["longitude"],
                  "latitude": rows[0]["latitude"], "observed_years": f"{rows[0]['year']}-{rows[-1]['year']}",
                  "observed_sequence": " → ".join(c or "missing" for c in classes)}
        if any(c is None for c in crops):
            excluded.append({**record, "reason": "Non-crop or unclassified in at least one year"})
            continue
        n = len(crops)
        record["previous_crop"] = crops[-1]
        record["current_projection"] = [crops[(plan_start + i - rows[0]["year"]) % n] for i in range(years)]
        record["observed_crops"] = crops
        parcels.append(record)
    return parcels, excluded


def corridor_parcels_from_output(workspace, corridor_output, corridor, plan_start, years):
    """B: CDL points in migration-corridor cells suitable in 2040–2049 that were cropland in every year 2019–2023."""
    import csv
    if corridor.get("source") != "corridor_grid" or not corridor.get("shift"):
        return [], "Corridor parcels need a trained model first: corridor --online."
    cells_path, points_path = Path(corridor_output) / "corridor_cells.csv", Path(corridor_output) / "corridor_points.csv"
    with cells_path.open(encoding="utf-8") as stream:
        cells = {r["cell_id"]: r for r in csv.DictReader(stream)}
    with points_path.open(encoding="utf-8") as stream:
        points = list(csv.DictReader(stream))
    if points and "cdl_sequence" not in points[0]:
        return [], "Corridor point sequences were saved by an older version; rebuild them with corridor --offline (no download needed)."
    out = []
    for pt in points:
        cell = cells.get(pt["cell_id"])
        if not cell or cell.get("suitable_future") not in ("1", "True", "true"):
            continue
        classes = pt["cdl_sequence"].split(" → ")
        crops = [economics.CDL_TO_CROP.get(c) for c in classes]
        if not crops or any(c is None for c in crops):
            continue
        lon, lat = float(pt["longitude"]), float(pt["latitude"])
        state = geo.state_of(lon, lat)
        if state is None:
            continue
        first_year = int(pt["cdl_years"].split("-")[0])
        out.append({"parcel_id": pt["point_id"], "region": state, "site": f"cell:{pt['cell_id']}", "kind": "corridor",
                    "cell_id": pt["cell_id"], "cell_lat": float(cell["latitude"]), "cell_lon": float(cell["longitude"]),
                    "longitude": lon, "latitude": lat, "observed_years": pt["cdl_years"],
                    "observed_sequence": pt["cdl_sequence"], "previous_crop": crops[-1], "observed_crops": crops,
                    "current_projection": [crops[(plan_start + i - first_year) % len(crops)] for i in range(years)]})
    return out, None


def make_feasibility(daily, calendar, plan_start, cache):
    """Winter wheat after a summer crop: the transition is infeasible if the earliest harvest of the previous crop is later than
    the latest sowing date of the wheat. Without information the transition is not blocked (and this is reported)."""
    memo = {}

    def feasible(previous, crop, index):
        if crop != "Winter Wheat" or previous in (None, "Winter Wheat", "Fallow/Idle Cropland"):
            return True
        key = (previous, index)
        if key not in memo:
            year = plan_start + index
            rule = calendar["crops"].get(previous, {})
            prev = planting.window(daily, previous, year - 1, calendar, cache)
            wheat = planting.window(daily, "Winter Wheat", year, calendar, cache)
            if rule.get("type") != "spring" or not rule.get("season_days") or not prev["start"] or not wheat["end"]:
                memo[key] = True
            else:
                harvest = date.fromisoformat(prev["start"]) + timedelta(days=int(rule["season_days"]))
                memo[key] = harvest <= date.fromisoformat(wheat["end"])
        return memo[key]
    return feasible


def run(workspace, economics_config_path, inputs_path, calendar_path, corridor_config_path, online=False):
    workspace = Path(workspace).resolve()
    econ_config = json.loads(Path(economics_config_path).read_text(encoding="utf-8"))
    economics.validate_config(econ_config)
    calendar = planting.load_calendar(calendar_path)
    plan_start, years = econ_config["plan_start_year"], econ_config["years"]
    plan_years = list(range(plan_start, plan_start + years))

    # A + D
    preloaded = suitability.load_pilot_observations(workspace)
    observations = preloaded[0]
    corridor_output, corridor = suitability.run(workspace, corridor_config_path, online, "auto", preloaded)

    # B: pilot parcels + migration-corridor parcels
    parcels, excluded = parcels_from_observations(observations, plan_start, years)
    for p in parcels:
        p["site"], p["kind"] = p["region"], "pilot"
    corridor_parcels, corridor_note = corridor_parcels_from_output(workspace, corridor_output, corridor, plan_start, years)
    parcels.extend(corridor_parcels)

    # E: climate and planting windows (per pilot site or corridor cell)
    corridor_cfg = json.loads(Path(corridor_config_path).read_text(encoding="utf-8"))
    sites = {}
    for p in parcels:
        sites.setdefault(p["site"], p)
    for region in econ_config["allowed_crops"]:
        if region.startswith("US"):
            sites.setdefault(region, {"site": region, "kind": "pilot", "region": region})
    daily, windows, caches, missing_chunks = {}, [], {}, {}
    for site, sample in sorted(sites.items()):
        if sample["kind"] == "pilot":
            daily[site], missing_chunks[site] = planting.load_site_daily(workspace, site, online=online)
        else:
            fetch = (lambda s_, a, b, c=sample: climate.get_point(workspace, f"grid:{c['cell_id']}", c["cell_lat"], c["cell_lon"], a, b,
                                                                  "projection", corridor_cfg["scenario"], online,
                                                                  {"dataset": "corridor_grid", "cell_id": c["cell_id"]})[0])
            daily[site], missing_chunks[site] = planting.load_site_daily(workspace, site, fetch=fetch)
        caches[site] = {}
    crops_needed = {}
    for site, sample in sorted(sites.items()):
        crops_needed[site] = sorted(set(econ_config["allowed_crops"].get(sample["region"], [])) |
                                    {c for p in parcels if p["site"] == site for c in p.get("current_projection", [])})
        for year in plan_years:
            for crop in crops_needed[site]:
                windows.append({"region": site, **planting.window(daily[site], crop, year, calendar, caches[site])})
    window_index = {(w["region"], w["crop"], w["plan_year"]): w for w in windows}

    # C
    manual = economics.load_inputs(inputs_path)
    nass, nass_provenance, nass_problems = economics.nass_inputs(workspace, econ_config, online)
    inputs = economics.merge_inputs(nass, manual)
    p_removal = economics.p_removal_by_crop(workspace)
    strategy_cache, plan_rows, strategy_rows, geo = {}, [], [], []
    for parcel in parcels:
        region, site = parcel["region"], parcel["site"]
        allowed = econ_config["allowed_crops"].get(region, [])
        feasible = make_feasibility(daily[site], calendar, plan_start, caches[site])
        initial_run = economics.years_without_fallow(parcel["observed_crops"])
        key = (region, site, parcel["previous_crop"], min(initial_run, 9))
        if key not in strategy_cache:
            strategy_cache[key] = economics.optimize(region, allowed, inputs, econ_config, p_removal,
                                                     parcel["previous_crop"], feasible, initial_run) if allowed else ([], [])
        ranked, incomplete = strategy_cache[key]
        wheat_need = max(econ_config.get("min_wheat_seasons", 0),
                         int(round(econ_config.get("wheat_focused_min_share", 0.5) * years)))
        best = ranked[0] if ranked else None
        wheat = next((r for r in ranked if sum(c in economics.WHEAT_CROPS for c in r["sequence"]) >= wheat_need
                      and (best is None or r["sequence"] != best["sequence"])), None)
        current = economics.evaluate(region, parcel["current_projection"], inputs, econ_config, p_removal, parcel["previous_crop"])
        chosen = {"current": current, "most_profitable": best, "wheat_focused": wheat}
        for name, result in chosen.items():
            if result is None:
                strategy_rows.append({"parcel_id": parcel["parcel_id"], "region": region, "site": site, "strategy": name,
                                      "sequence": None, "total_profit_usd_per_acre": None,
                                      "cumulative_p_removal_kg_per_ha": None,
                                      "status": "awaiting_inputs",
                                      "missing_inputs": "; ".join(incomplete) or "no valid sequence"})
                continue
            strategy_rows.append({"parcel_id": parcel["parcel_id"], "region": region, "site": site, "strategy": name,
                                  "sequence": " → ".join(result["sequence"]),
                                  "total_profit_usd_per_acre": result["total_profit_usd_per_acre"],
                                  "cumulative_p_removal_kg_per_ha": result["cumulative_p_removal_kg_per_ha"],
                                  "status": "ok" if result["total_profit_usd_per_acre"] is not None else "awaiting_inputs",
                                  "missing_inputs": "; ".join(result["missing_inputs"])})
            for year, item in zip(plan_years, result["yearly"]):
                w = window_index.get((site, item["crop"], year), {})
                plan_rows.append({"parcel_id": parcel["parcel_id"], "region": region, "site": site, "strategy": name, "plan_year": year,
                                  "crop": item["crop"], "planting_start": w.get("start"), "planting_end": w.get("end"),
                                  "planting_status": w.get("status"), "planting_basis": w.get("basis"),
                                  "planting_detail": w.get("detail"),
                                  "expected_profit_usd_per_acre": item["profit_usd_per_acre"],
                                  "p_removal_kg_per_ha": item["p_removal_kg_per_ha"],
                                  "missing_inputs": "; ".join(item["missing"])})
        recommended = best or current
        first = recommended["yearly"][0]
        w = window_index.get((site, first["crop"], plan_start), {})
        geo.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [parcel["longitude"], parcel["latitude"]]},
                    "properties": {"parcel_id": parcel["parcel_id"], "region": region, "site": site, "kind": parcel["kind"],
                                   "observed_years": parcel.get("observed_years"),
                                   "observed_sequence": parcel["observed_sequence"],
                                   "current_rotation": " → ".join(current["sequence"]),
                                   "best_rotation": " → ".join(best["sequence"]) if best else None,
                                   "economic_status": "ok" if best else "awaiting_inputs",
                                   f"crop_{plan_start}": first["crop"], f"planting_start_{plan_start}": w.get("start"),
                                   f"planting_end_{plan_start}": w.get("end")}})

    # C/D: climate-to-yield model — most profitable plan with 2040s yields on corridor parcels
    yield_output, multipliers, yield_rows = yieldmodel.latest_multipliers(workspace)
    future_cache, future_summary = {}, {"parcels": 0, "changed": 0, "examples": []}
    for parcel in (p for p in parcels if p["kind"] == "corridor"):
        region, cell = parcel["region"], parcel.get("cell_id")
        allowed = econ_config["allowed_crops"].get(region, [])
        factors = {c: multipliers[(cell, c)] for c in allowed if (cell, c) in multipliers}
        if not allowed or not factors:
            continue
        fkey = (region, cell, parcel["previous_crop"], min(economics.years_without_fallow(parcel["observed_crops"]), 9))
        if fkey not in future_cache:
            adjusted = dict(inputs)
            for crop, m in factors.items():
                entry = inputs.get((region, crop))
                if entry and entry.get("yield") is not None:
                    adjusted[(region, crop)] = {**entry, "yield": entry["yield"] * m}
            feasible = make_feasibility(daily[parcel["site"]], calendar, plan_start, caches[parcel["site"]])
            future_cache[fkey] = economics.optimize(region, allowed, adjusted, econ_config, p_removal, parcel["previous_crop"],
                                                    feasible, fkey[-1])[0]
        ranked = future_cache[fkey]
        if not ranked:
            continue
        top = ranked[0]
        today = next((r for r in strategy_rows if r["parcel_id"] == parcel["parcel_id"] and r["strategy"] == "most_profitable"), None)
        seq = " → ".join(top["sequence"])
        strategy_rows.append({"parcel_id": parcel["parcel_id"], "region": region, "site": parcel["site"], "strategy": "most_profitable_2040",
                              "sequence": seq, "total_profit_usd_per_acre": top["total_profit_usd_per_acre"],
                              "cumulative_p_removal_kg_per_ha": top["cumulative_p_removal_kg_per_ha"], "status": "ok",
                              "missing_inputs": "yield multipliers: " + ", ".join(f"{c} ×{m:.2f}" for c, m in sorted(factors.items()))})
        future_summary["parcels"] += 1
        if today and today["sequence"] and today["sequence"] != seq:
            future_summary["changed"] += 1
            if len(future_summary["examples"]) < 5:
                future_summary["examples"].append({"parcel_id": parcel["parcel_id"], "today": today["sequence"], "future": seq})

    # Price sensitivity (C): most profitable plan per region in each scenario, and the difference to the current plan
    sensitivity, sens_cache = [], {}
    for factor in econ_config.get("price_scenarios", [1.0]):
        for region in sorted({p["region"] for p in parcels}):
            allowed = econ_config["allowed_crops"].get(region, [])
            bests, currents, seqs = [], [], {}
            for parcel in (x for x in parcels if x["region"] == region):
                feasible = make_feasibility(daily[parcel["site"]], calendar, plan_start, caches[parcel["site"]])
                skey = (factor, region, parcel["site"], parcel["previous_crop"], economics.years_without_fallow(parcel["observed_crops"]))
                if skey not in sens_cache:
                    sens_cache[skey] = economics.optimize(region, allowed, inputs, econ_config, p_removal, parcel["previous_crop"], feasible,
                                                         skey[-1], factor) if allowed else ([], [])
                ranked, _ = sens_cache[skey]
                cur = economics.evaluate(region, parcel["current_projection"], inputs, econ_config, p_removal, parcel["previous_crop"], factor)
                if ranked:
                    bests.append(ranked[0]["total_profit_usd_per_acre"])
                    key = " → ".join(ranked[0]["sequence"]); seqs[key] = seqs.get(key, 0) + 1
                if cur["total_profit_usd_per_acre"] is not None:
                    currents.append(cur["total_profit_usd_per_acre"])
            sensitivity.append({"price_factor": factor, "region": region,
                                "best_mean_profit": round(sum(bests) / len(bests), 1) if bests else None,
                                "current_mean_profit": round(sum(currents) / len(currents), 1) if currents else None,
                                "typical_best_sequence": max(seqs, key=seqs.get) if seqs else None})
    write_csv_rows = sensitivity

    # Component status
    econ_ready = any(r["strategy"] == "most_profitable" and r["status"] == "ok" for r in strategy_rows)
    readiness = corridor["readiness"]
    needs = [w for w in windows if w["status"] != "no_planting"]
    ok_windows = sum(w["status"] == "ok" for w in needs)
    start_only = sum(w["status"] in ("start_only", "low_confidence") for w in needs)
    no_rule = sorted({w["crop"] for w in needs if w["status"] == "no_rule"})
    status = {
        "A": {"status": "working" if corridor["shift"] else "awaiting_data",
              "produced": (f"Suitability centre shifts {corridor['shift']['distance_km']:.0f} km at {corridor['shift']['bearing_deg']:.0f}°"
                           if corridor["shift"] else "Reference → future climate difference computed per cell; the shift vector needs a trained model"),
              "next": "Widen the box: config/corridor.json bbox → corridor --online" if corridor["shift"] else "python3 -m fieldshift_data corridor --online (downloads the corridor grid from NASA and USDA)"},
        "B": {"status": "working",
              "produced": (f"{sum(p['kind'] == 'pilot' for p in parcels)} pilot parcels + {sum(p['kind'] == 'corridor' for p in parcels)} migration-corridor parcels"
                           + (f" ({', '.join(sorted({p['region'] for p in parcels if p['kind'] == 'corridor'}))})" if corridor_parcels else "")
                           + f"; {len(excluded)} pilot points are non-cropland"),
              "next": corridor_note or "Corridor parcels were built from the 2040–2049 suitable zone"},
        "C": {"status": "working" if econ_ready else "awaiting_inputs",
              "produced": "Profit optimisation and 3 strategies computed" if econ_ready else
                          "Optimiser ready; waiting for yield/price/cost inputs",
              "next": "Fill config/economics_inputs.csv with sources, or run economics --online with FIELDSHIFT_NASS_KEY"},
        "D": {"status": "trained" if readiness["trained"] else "insufficient_training_data",
              "produced": (f"Logistic model, spatial block validation AUC={corridor['validation']['auc']:.3f}"
                           if readiness["trained"] and corridor["validation"]["auc"] is not None else "; ".join(readiness["reasons"])),
              "next": "corridor --online with at least 12 cells of different climate"},
        "E": {"status": "working" if ok_windows else "awaiting_data",
              "produced": (f"Of {len(needs)} region-crop-years that need planting, {ok_windows} have a full window and {start_only} only a start or low confidence"
                           + (f"; crops without a rule: {', '.join(no_rule)}" if no_rule else "")),
              "next": "Source thresholds are in config/crop_calendar.json; validate with local soil temperature"},
    }
    if yield_output:
        status["C"]["produced"] += (f"; climate→yield model ({yield_output}): plan with 2040s yields on {future_summary['parcels']} corridor parcels, "
                                    f"most profitable rotation changes on {future_summary['changed']}")
    else:
        status["C"]["next"] += "; for the climate→yield model: yield-model --online (needs a NASS key)"
    output = workspace / "outputs" / ("goal_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    write_csv(output / "parcel_plans.csv", plan_rows)
    write_csv(output / "parcel_strategies.csv", strategy_rows)
    write_csv(output / "planting_windows.csv", windows)
    write_csv(output / "parcels_excluded.csv", excluded)
    write_csv(output / "price_sensitivity.csv", write_csv_rows)
    write_json(output / "parcels.geojson", {"type": "FeatureCollection", "features": geo})
    report = {"goal": GOAL_TEXT, "components": COMPONENTS, "status": status, "plan_years": plan_years,
              "parcels": len(parcels), "corridor_parcels": len(corridor_parcels), "corridor_parcel_note": corridor_note, "excluded_points": len(excluded), "corridor_output": corridor_output.name,
              "corridor": {k: corridor[k] for k in ("source", "source_note", "readiness", "validation", "shift")},
              "economics": {"config_sha256": digest(economics_config_path),
                            "inputs_sha256": digest(inputs_path) if Path(inputs_path).is_file() else None,
                            "nass_series_cached": len(nass_provenance), "nass_problems": nass_problems[:20],
                            "p_removal_kg_per_ha": p_removal,
                            "rotation_effects": econ_config.get("rotation_effects", [])},
              "price_sensitivity": sensitivity,
              "yield_model": {"output": yield_output, "usable_multipliers": len(multipliers), "future_plans": future_summary},
              "calendar_sha256": digest(calendar_path), "climate_missing_chunks": missing_chunks,
              "validation_note": "In the Oregon USOR03 source record, winter wheat was sown on 15 October 2018; the window computed for that year is compared with it.",
              "oregon_2019_window": (planting.window(daily["USOR03"], "Winter Wheat", 2019, calendar, caches["USOR03"])
                                     if "USOR03" in daily else None),
              "limitations": [
                  "The current rotation is assumed to be the cyclic continuation of the 2018–2023 CDL sequence.",
                  "Parcels in one region share the same county yield, price and cost; parcels differ only by their crop history.",
                  "Rotation effects on yield enter only through sourced rotation_effects rows; currently wheat after wheat in Oregon (Maaz et al. 2017).",
                  "Planting windows use air temperature as a proxy for soil temperature and rely on the NEX-GDDP ensemble mean.",
                  "This tool supports decisions; it does not replace the judgement of the farmer or a local expert."]}
    write_json(output / "goal.json", report)
    write_report(output, report, strategy_rows, plan_rows, windows, parcels, plan_start)
    return output, report


def write_report(output, report, strategy_rows, plan_rows, windows, parcels, plan_start):
    label = {"working": "Working", "awaiting_inputs": "Awaiting inputs", "awaiting_data": "Awaiting data",
             "trained": "Trained", "insufficient_training_data": "Insufficient training data"}
    lines = ["# FieldShift goal report", "", "**Project goal (Preparation.md):** " + report["goal"], "",
             "## Status of the goal components", "", "| Component | Status | Produced | To complete |", "|---|---|---|---|"]
    for key, name in report["components"].items():
        s = report["status"][key]
        lines.append(f"| {key}. {name} | {label.get(s['status'], s['status'])} | {s['produced']} | `{s['next']}` |")
    lines += ["", "## Planting windows (E)", "", "For winter wheat the plan year is the harvest year; sowing is in the previous autumn.", "",
              "| Region | Year | Crop | Start | End | Status | Basis |", "|---|---|---|---|---|---|---|"]
    for w in windows:
        if w["plan_year"] in (plan_start, plan_start + 1):
            lines.append(f"| {w['region']} | {w['plan_year']} | {w['crop']} | {w['start'] or '—'} | {w['end'] or '—'} | {w['status']} | {w['basis'] or ''} |")
    check = report.get("oregon_2019_window")
    if check:
        lines += ["", f"**Check against the source record:** Oregon USOR03 winter wheat was sown on 15 October 2018. Computed window for harvest year 2019: "
                      f"{check['start']} – {check['end']} ({check['basis']})."]
    lines += ["", "## Parcel strategies (C)", "", f"{report['parcels']} parcels; {report['excluded_points']} points were not counted as parcels because they are non-cropland.", ""]
    by_region = {}
    for row in strategy_rows:
        by_region.setdefault((row["region"], row["strategy"]), []).append(row)
    lines += ["| Region | Strategy | Example sequence | Total profit (USD/acre) | Status / missing |", "|---|---|---|---|---|"]
    for (region, strategy), rows in sorted(by_region.items()):
        r = rows[0]
        profit = "—" if r["total_profit_usd_per_acre"] is None else f"{r['total_profit_usd_per_acre']:.0f}"
        missing = r["missing_inputs"] if r["missing_inputs"] else ""
        if len(missing) > 140:
            missing = missing[:140] + "…"
        lines.append(f"| {region} | {strategy} | {r['sequence'] or '—'} | {profit} | {r['status']}: {missing} |")
    if report.get("price_sensitivity"):
        lines += ["", "### Price scenarios (±20% of source prices; sensitivity assumption)", "",
                  "| Region | Price factor | Typical most profitable sequence | Mean most profitable $/acre | Mean current $/acre |", "|---|---:|---|---:|---:|"]
        for r in report["price_sensitivity"]:
            f = lambda v: "—" if v is None else f"{v:.0f}"
            lines.append(f"| {r['region']} | {r['price_factor']} | {r['typical_best_sequence'] or '—'} | {f(r['best_mean_profit'])} | {f(r['current_mean_profit'])} |")
    ym = report.get("yield_model") or {}
    if ym.get("output"):
        fp = ym["future_plans"]
        lines += ["", "### Yield under a changing climate (C/D: climate-to-yield model)", "",
                  f"Model output `{ym['output']}`; {ym['usable_multipliers']} cell×crop multipliers usable. "
                  f"Most profitable plan with 2040–2049 yields computed for {fp['parcels']} corridor parcels (`most_profitable_2040`); "
                  f"it differs from today's most profitable rotation on {fp['changed']} parcels.", ""]
        if fp["examples"]:
            lines += ["| Parcel | Most profitable today | Most profitable with 2040s yields |", "|---|---|---|"]
            lines += [f"| {e['parcel_id']} | {e['today']} | {e['future']} |" for e in fp["examples"]]
    lines += ["", "All parcels and years: `parcel_plans.csv`, `parcel_strategies.csv`; for maps: `parcels.geojson`.", "",
              "## P removal (soil nutrient balance constraint)", "", "| Crop | kg P/ha/yr (median) | Systems | Range |", "|---|---:|---:|---|"]
    for crop, item in sorted(report["economics"]["p_removal_kg_per_ha"].items()):
        lines.append(f"| {crop} | {item['kg_p_per_ha']:.1f} | {item['systems']} | {item['min']:.1f}–{item['max']:.1f} |")
    lines += ["", "## Limits of interpretation", "", *["- " + x for x in report["limitations"]], ""]
    (output / "GOAL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def at_date(output_dir, when, strategy="most_profitable"):
    """Status of each parcel on the chosen date: that year's crop and its position relative to the planting window."""
    import csv
    year = when.year
    with (Path(output_dir) / "parcel_plans.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    available = {r["parcel_id"] for r in rows if r["strategy"] == strategy}
    answer = []
    for row in rows:
        used = strategy if row["parcel_id"] in available else "current"
        if row["strategy"] != used:
            continue
        crop_year = int(row["plan_year"])
        relevant = crop_year == year or (row["crop"] == "Winter Wheat" and crop_year == year + 1)
        if not relevant:
            continue
        start, end = row["planting_start"], row["planting_end"]
        if start and end:
            state = ("in planting window" if start <= when.isoformat() <= end else
                     "before window" if when.isoformat() < start else "window passed")
        else:
            state = row["planting_status"] or "unknown"
        answer.append({"parcel_id": row["parcel_id"], "strategy": used, "plan_year": crop_year, "crop": row["crop"],
                       "planting_start": start or None, "planting_end": end or None, "state_on_date": state})
    order = {"in planting window": 0, "before window": 1}
    answer.sort(key=lambda r: (order.get(r["state_on_date"], 2), r["parcel_id"]))
    return answer
