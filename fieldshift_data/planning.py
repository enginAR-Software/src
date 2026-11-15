"""Optimize cyclic scenarios from observed rotations; no invented crop effects."""

from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from uuid import uuid4

from . import __version__
from .catalog import SOURCES, source_directory
from .download import validate_cache
from .pflux import prepare
from .tables import digest, read_csv, write_csv, write_json


def validate(config):
    c = dict(config)
    if c["mode"] != "reference_scenario":
        raise ValueError("This version computes a reference scenario from observed rotations; a field-advice mode has not been calibrated.")
    for key, low, high in (("years", 1, 30), ("start_year", 1900, 2100), ("top_k", 1, 20),
                           ("minimum_wheat_seasons", 0, c["years"]), ("minimum_distinct_crop_labels", 1, 30)):
        value = c[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"{key}: integer in {low}..{high} required.")
    for key in ("max_annual_p_application", "max_abs_cumulative_p_change"):
        try:
            value = float(c[key])
        except (TypeError, ValueError) as error:
            raise ValueError(f"{key}: numeric limit required.") from error
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{key}: finite, non-negative limit required.")
        c[key] = value
    if c["budget_basis"] not in ("field_tp", "agronomic"):
        raise ValueError("budget_basis must be field_tp or agronomic.")
    if not isinstance(c["allowed_crops"], list) or not c["allowed_crops"] or not all(isinstance(x, str) and x for x in c["allowed_crops"]):
        raise ValueError("allowed_crops: explicit allowed crop names required.")
    if not isinstance(c["require_complete_cycles"], bool):
        raise ValueError("require_complete_cycles must be true/false.")
    if not isinstance(c["previous_crop"], str):
        raise ValueError("previous_crop must be text.")
    return c


def solve(rows, config):
    c = validate(config)
    grouped = defaultdict(list)
    for row in rows:
        if row["location"] == c["location"] and row["record_type"] == "rotation_position":
            grouped[row["system_id"]].append(row)
    if not grouped:
        raise ValueError("No rotation found in the selected source region.")
    candidates, excluded = [], []
    budget_key = "overall_p_budget" if c["budget_basis"] == "field_tp" else "agronomic_p_budget"
    for sid, records in sorted(grouped.items()):
        cycle = sorted(records, key=lambda r: r["rotation_position"])
        reasons = []
        if [r["rotation_position"] for r in cycle] != list(range(1, len(cycle) + 1)):
            reasons.append("incomplete_rotation_positions")
        if any(r["crop"] not in c["allowed_crops"] for r in cycle):
            reasons.append("crop_not_allowed")
        if c["require_complete_cycles"] and c["years"] % len(cycle):
            reasons.append("horizon_not_complete_cycles")
        if any(r[budget_key] is None for r in cycle):
            reasons.append("missing_budget")
        if c["budget_basis"] == "field_tp" and any(r["hydrologic_p_form"].strip() != "TP" for r in cycle):
            reasons.append("total_p_loss_not_available")
        if any(r["application_p"] is None or r["application_p"] > c["max_annual_p_application"] for r in cycle):
            reasons.append("annual_p_application_limit")
        if reasons:
            excluded.append({"system_id": sid, "start_position": None, "reason": ";".join(reasons)})
            continue
        for offset in range(len(cycle)):
            schedule = []
            cumulative = 0.0
            for year in range(c["years"]):
                source = cycle[(offset + year) % len(cycle)]
                before = cumulative
                cumulative += source[budget_key]
                schedule.append({"plan_year": c["start_year"] + year, "system_id": sid,
                                 "source_rotation_position": source["rotation_position"], "crop": source["crop"],
                                 "source_mean_application_p": source["application_p"],
                                 "source_mean_net_p": source[budget_key],
                                 "cumulative_p_change_before": before, "cumulative_p_change_after": cumulative})
            reasons = []
            wheat = sum("wheat" in r["crop"].casefold() for r in schedule)
            if wheat < c["minimum_wheat_seasons"]:
                reasons.append("minimum_wheat_seasons")
            if len({r["crop"] for r in schedule}) < c["minimum_distinct_crop_labels"]:
                reasons.append("minimum_crop_label_diversity")
            if c["previous_crop"] and schedule[0]["crop"].casefold() == c["previous_crop"].casefold():
                reasons.append("previous_crop_repeated_at_boundary")
            peak = max(abs(r["cumulative_p_change_after"]) for r in schedule)
            if peak > c["max_abs_cumulative_p_change"] + 1e-9:
                reasons.append("cumulative_p_change_limit")
            if reasons:
                excluded.append({"system_id": sid, "start_position": offset + 1, "reason": ";".join(reasons)})
                continue
            candidates.append({"system_id": sid, "system_name": cycle[0]["system_name"], "start_position": offset + 1,
                               "wheat_seasons": wheat, "sum_abs_cumulative_p_change": sum(abs(r["cumulative_p_change_after"]) for r in schedule),
                               "peak_abs_cumulative_p_change": peak, "final_cumulative_p_change": cumulative,
                               "total_source_mean_p_application": sum(r["source_mean_application_p"] for r in schedule),
                               "schedule": schedule})
    candidates.sort(key=lambda r: (r["sum_abs_cumulative_p_change"], r["total_source_mean_p_application"], r["system_id"], r["start_position"]))
    return {"status": "ok" if candidates else "no_feasible_plan", "settings": c,
            "recommendation_readiness": "reference_only",
            "unresolved_inputs": ["field-specific N/K and available P states", "crop response to projected climate",
                                  "crop yield and production requirements", "sowing windows and within-year crop timing"],
            "candidate_systems": len(grouped), "feasible_scenarios": len(candidates),
            "objective": "minimize sum of absolute cumulative net P changes, then source-mean P inputs",
            "units": "kg elemental P/ha; changes from zero accounting baseline, NOT available soil stocks",
            "assumptions": ["Observed rotation order and management are preserved; cyclic phase may change.",
                            "Each rotation position is assigned one planning season/year; crop-specific sowing dates are unresolved.",
                            "Source average flows repeat unchanged; climate response, N/K dynamics and yield changes are not predicted."],
            "best": candidates[:c["top_k"]],
            "candidates": [{k: v for k, v in r.items() if k != "schedule"} for r in candidates], "excluded": excluded}


def at_date(plan, date):
    if not plan["best"]:
        return None
    return next((row for row in plan["best"][0]["schedule"] if row["plan_year"] == date.year), None)


def run(workspace, config_path):
    workspace, config_path = Path(workspace).resolve(), Path(config_path)
    source = validate_cache(workspace, "pflux")
    directory = source_directory(workspace, "pflux")
    tables = [read_csv((directory / name).read_bytes(), name) for name in ("PBudgetData.csv", "DataSourcesAndReferences.csv")]
    rows, _, _ = prepare(*tables)
    result = solve(rows, json.loads(config_path.read_text(encoding="utf-8")))
    now = datetime.now(timezone.utc)
    output = workspace / "outputs" / ("plan_" + now.strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    result.update(software_version=__version__, created_at_utc=now.isoformat(), provenance=source,
                  config_sha256=digest(config_path), data_mode="observed_rotation_reference_scenario")
    write_json(output / "plan.json", result)
    schedule = [{"rank": rank, **row} for rank, candidate in enumerate(result["best"], 1) for row in candidate["schedule"]]
    write_csv(output / "schedule.csv", schedule, ["rank", "plan_year", "system_id", "source_rotation_position", "crop", "source_mean_application_p", "source_mean_net_p", "cumulative_p_change_before", "cumulative_p_change_after"])
    write_csv(output / "candidates.csv", result["candidates"], ["system_id", "system_name", "start_position", "wheat_seasons", "sum_abs_cumulative_p_change", "peak_abs_cumulative_p_change", "final_cumulative_p_change", "total_source_mean_p_application"])
    write_csv(output / "excluded.csv", result["excluded"], ["system_id", "start_position", "reason"])
    lines = ["# FieldShift rotation scenario", "", f"Status: {result['status']}", "",
             f"Location group in the source: {result['settings']['location']}. {result['feasible_scenarios']} feasible phase scenarios. This label alone does not prove the same parcel or a shared climate.", "",
             "Objective: minimise the sum of absolute deviations of the cumulative P input-output difference from zero. Limits are a user scenario, not agronomic sufficiency thresholds.", "",
             "This output is a reference scenario that places observed cycles into the planning years. The cumulative change is not a plant-available soil P stock. Source means are assumed to continue unchanged; climate effects are not yet linked to this budget.", ""]
    if result["best"]:
        best = result["best"][0]
        lines += [f"Selected system: {best['system_id']}, source start position {best['start_position']}.", "",
                  "| Plan year | Crop | Mean P input | Net P | Cumulative change |", "|---|---|---:|---:|---:|"]
        lines += [f"| {r['plan_year']} | {r['crop']} | {r['source_mean_application_p']:.2f} | {r['source_mean_net_p']:.2f} | {r['cumulative_p_change_after']:.2f} |" for r in best["schedule"]]
    else:
        lines += ["No scenario meets the conditions. Exclusion reasons are in `excluded.csv`."]
    lines += ["", "No day/month planting calendar, yield forecast or field fertilizer rate is produced. Without N/K, water, disease, economic production and climate suitability, this is not an overall soil-fertility ranking.", "", SOURCES["pflux"]["doi"], ""]
    (output / "PLAN_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return output, result
