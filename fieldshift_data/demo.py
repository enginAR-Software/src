"""One-command usage demo: runs the whole FieldShift chain offline and prints what a farmer would see.

    python3 -m fieldshift_data demo [--open]

Steps:
  1. goal      — components A–E on the packaged data (and on corridor data if it was downloaded before)
  2. dashboard — DASHBOARD.html
  3. app       — FieldShift_App.html (interactive map)
  4. summary   — example parcel plan, a date query and the migration result, also written to DEMO.md

No internet connection is needed. Nothing is invented: every number comes from the goal output.
"""

import csv
from datetime import date
import json
from pathlib import Path

from . import app, dashboard, goal, suitability

REFERENCE_CELLS = Path(__file__).resolve().parent.parent / "data/reference/corridor_cells_full_run.csv"
STATUS = {"working": "working", "awaiting_inputs": "awaiting inputs", "awaiting_data": "awaiting data",
          "trained": "trained", "insufficient_training_data": "insufficient training data"}

CROP = {"Winter Wheat": "winter wheat", "Spring Wheat": "spring wheat", "Corn": "corn", "Soybeans": "soybeans",
        "Sorghum": "sorghum", "Peas": "peas", "Fallow/Idle Cropland": "fallow", "Alfalfa": "alfalfa"}


def _crop(name):
    return CROP.get(name, name)


def _rows(path):
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def summary(output):
    """Plain-language summary of a goal output, as a list of Markdown lines."""
    report = json.loads((output / "goal.json").read_text(encoding="utf-8"))
    plans = _rows(output / "parcel_plans.csv")
    strategies = _rows(output / "parcel_strategies.csv")
    lines = ["# FieldShift usage demo", "", f"Goal output: `{output.name}`", "",
             "## 1. Status of the five goal components", ""]
    for key, item in report["status"].items():
        lines.append(f"- **{key}. {report['components'][key]}** — {STATUS.get(item['status'], item['status'])}: {item['produced']}")

    lines += ["", "## 2. Example: what one farmer is told", ""]
    for region, name in (("USKS01", "Kansas pilot (near Manhattan, KS)"), ("USOR03", "Oregon pilot (near Pendleton, OR)")):
        best = [r for r in strategies if r["region"] == region and r["strategy"] == "most_profitable" and r["status"] == "ok"]
        if not best:
            lines.append(f"- {name}: economic inputs missing; see GOAL_REPORT.md.")
            continue
        parcel = sorted(best, key=lambda r: r["parcel_id"])[0]
        current = next((r for r in strategies if r["parcel_id"] == parcel["parcel_id"] and r["strategy"] == "current"), None)
        years = [r for r in plans if r["parcel_id"] == parcel["parcel_id"] and r["strategy"] == "most_profitable"]
        years.sort(key=lambda r: int(r["plan_year"]))
        lines += [f"### {name}, parcel `{parcel['parcel_id']}`", "",
                  f"Recommended 6-year rotation: **{' → '.join(_crop(c) for c in parcel['sequence'].split(' → '))}**, "
                  f"total profit {float(parcel['total_profit_usd_per_acre']):.0f} $/acre"
                  + (f" (current rotation: {float(current['total_profit_usd_per_acre']):.0f} $/acre)."
                     if current and current["total_profit_usd_per_acre"] else "."), "",
                  "| Year | Plant | Planting window |", "|---|---|---|"]
        for r in years:
            window = (f"{r['planting_start']} – {r['planting_end']}" if r["planting_start"] and r["planting_end"]
                      else f"from {r['planting_start']}" if r["planting_start"] else "no planting")
            lines.append(f"| {r['plan_year']} | {_crop(r['crop'])} | {window} |")
        lines.append("")

    when = date(int(report["plan_years"][0]), 4, 20)
    rows = goal.at_date(output, when)
    in_window = [r for r in rows if r["state_on_date"] == "in planting window"]
    parcels = {r["parcel_id"] for r in in_window}
    lines += ["## 3. Date query", "", f"On {when.isoformat()}, {len(parcels)} parcels are in their planting window"
              + (" for: " + ", ".join(sorted({_crop(r['crop']) for r in in_window})) + "." if in_window else "."),
              f"Command: `python3 -m fieldshift_data goal-view {output.name} --date {when.isoformat()}`", ""]

    corridor = report.get("corridor") or {}
    zone = (corridor.get("shift") or {}).get("suitable_zone")
    lines += ["## 4. Where wheat is moving", ""]
    if zone:
        auc = (corridor.get("validation") or {}).get("auc")
        if corridor.get("source") == "reference_full_run":
            lines.append("Source: the cell table of the team's full online corridor run (USDA CDL 2019–2023 labels × NASA NEX-GDDP "
                         "features), packaged in `data/reference/`; the model is retrained on it here.")
        lines.append(f"Suitable wheat zone: {zone['cells_baseline']} → {zone['cells_future']} one-degree cells; its centre moves "
                     f"{zone['distance_km']:.0f} km at {zone['bearing_deg']:.0f}° (0° = north) between 2015–2024 and 2040–2049"
                     + (f". Spatial cross-validation AUC {auc:.3f}." if auc is not None else "."))
    else:
        lines.append("Corridor data not downloaded yet. Run `python3 -m fieldshift_data corridor --online` once "
                     "(about 1–2 hours), then run the demo again.")
    lines += ["", "## 5. Files to open", "", "- `FieldShift_App.html` — interactive map, parcel plans, date query, farmer priorities",
              "- `DASHBOARD.html` — goal dashboard", "- `GOAL_REPORT.md` — full report with sources and limitations", ""]
    return lines


def attach_reference_corridor(workspace, output, corridor_config):
    """If no corridor cache exists, retrain the suitability model on the packaged cell table of the team's full run
    and attach the result to the goal output (components A and D). Returns True when attached."""
    report = json.loads((output / "goal.json").read_text(encoding="utf-8"))
    if (report.get("corridor") or {}).get("shift") or not REFERENCE_CELLS.is_file():
        return False
    config = json.loads(Path(corridor_config).read_text(encoding="utf-8"))
    rows = _rows(REFERENCE_CELLS)
    cells, points = [], []
    for r in rows:
        cells.append({"cell_id": r["cell_id"], "row": int(r["cell_id"][1:3]), "col": int(r["cell_id"][4:6]), "block": r["block"],
                      "longitude": float(r["longitude"]), "latitude": float(r["latitude"]),
                      "baseline": {f: float(r["baseline_" + f]) for f in suitability.FEATURES},
                      "future": {f: float(r["future_" + f]) for f in suitability.FEATURES}, "baseline_ok": True, "future_ok": True})
        wheat, crop = int(r["wheat_points"]), int(r["cropland_points"])
        points += [{"cell_id": r["cell_id"], "label": 1}] * wheat + [{"cell_id": r["cell_id"], "label": 0}] * (crop - wheat)
    result = suitability.analyse(cells, points, config)
    folder = Path(workspace) / "outputs" / "corridor_reference_full_run"
    folder.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with (folder / "corridor_cells.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields + [k for k in ("suitability_baseline", "suitability_future",
                                                                          "suitability_change", "suitable_baseline", "suitable_future") if k not in fields])
        writer.writeheader()
        by_id = {c["cell_id"]: c for c in cells}
        for r in rows:
            c = by_id[r["cell_id"]]
            writer.writerow({**r, **{k: c.get(k, r.get(k)) for k in ("suitability_baseline", "suitability_future", "suitability_change",
                                                                     "suitable_baseline", "suitable_future")}})
    zone = result["shift"]["suitable_zone"]
    auc = result["validation"]["auc"]
    report["corridor_output"] = folder.name
    report["corridor"] = {"source": "reference_full_run", "source_note": "Cell table of the team's full online run, packaged in data/reference/",
                          "readiness": result["readiness"], "validation": result["validation"], "shift": result["shift"]}
    report["status"]["A"].update({"status": "working", "produced": f"Suitable zone {zone['cells_baseline']} → {zone['cells_future']} cells; "
                                  f"centre shifts {zone['distance_km']:.0f} km at {zone['bearing_deg']:.0f}° (reference full run)"})
    report["status"]["D"].update({"status": "trained", "produced": f"Logistic model, spatial block validation AUC={auc:.3f} (reference full run)"})
    (output / "goal.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "GOAL_REPORT.md").open("a", encoding="utf-8") as stream:
        stream.write("\n## Components A and D from the reference full run (added by the demo)\n\n"
                     "No corridor cache was found on this machine, so the suitability model was retrained on the packaged cell table "
                     "of the team's full online run (`data/reference/corridor_cells_full_run.csv`: USDA CDL 2019–2023 wheat labels × "
                     "NASA NEX-GDDP SSP2-4.5 cell climate). The status table above was written before this step.\n\n"
                     f"- Spatial block cross-validation AUC: {auc:.3f} (0.5 = random)\n"
                     f"- Suitable zone (probability ≥ {zone['threshold']}): {zone['cells_baseline']} → {zone['cells_future']} cells; "
                     f"gained {zone['cells_gained']}, lost {zone['cells_lost']}\n"
                     f"- Zone centre shift: {zone['distance_km']:.1f} km at {zone['bearing_deg']:.0f}° (0° north)\n"
                     + ("- Warning: the suitable zone touches the edge of the study box; the shift may be larger.\n" if zone.get("touches_box_edge") else ""))
    return True


def run(workspace, economics_config, inputs, calendar, corridor_config):
    workspace = Path(workspace).resolve()
    print("Step 1/3: goal (components A–E) ...", flush=True)
    output, _ = goal.run(workspace, economics_config, inputs, calendar, corridor_config, False)
    if attach_reference_corridor(workspace, output, corridor_config):
        print("No corridor cache found: using the packaged cell table of the team's full online run for components A and D.", flush=True)
    print("Step 2/3: dashboard ...", flush=True)
    board, _ = dashboard.build(output, workspace, calendar)
    print("Step 3/3: interactive app ...", flush=True)
    page, _ = app.build(workspace, output, economics_config, inputs, calendar)
    lines = summary(output)
    lines[-4:-1] = [f"- `{page}` — interactive map, parcel plans, date query, farmer priorities",
                    f"- `{board}` — goal dashboard", f"- `{output / 'GOAL_REPORT.md'}` — full report with sources and limitations"]
    (output / "DEMO.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output, page, lines
