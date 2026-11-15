"""Components C/D: climate-to-yield model and 2040s yield multipliers.

Question: how much does each crop's yield change in the corridor as the climate changes?
Method:
    1. USDA NASS Quick Stats county yields (SURVEY, COUNTY, 10-year mean).
    2. County centroids (US Census boundaries, us-atlas) are placed into the corridor's 1° cells;
          cell yield = mean of its counties.
    3. Ridge regression with quadratic temperature terms between the cell's reference climate
          (NASA NEX-GDDP 2015–2024, corridor output) and yield; spatial block cross-validation.
    4. The same model is applied to the future climate (2040–2049): multiplier = future prediction / reference prediction.
The multiplier is clipped to [0.5, 1.5]; climates outside the training range are flagged as extrapolation.
No yield is invented: without a NASS cache the model is not built and the reason is reported.
"""

import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from uuid import uuid4

from . import economics, geo
from .suitability import FEATURES
from .tables import write_csv, write_json

ASSET_CENTROIDS = Path(__file__).parent / "assets" / "county_centroids.csv"
CROPS = ["Winter Wheat", "Spring Wheat", "Corn", "Soybeans", "Sorghum"]
YEARS = (2014, 2023)
MIN_CELLS = 8
CLIP = (0.5, 1.5)


def county_args(crop, state, years=YEARS):
    return {"short_desc": economics.NASS_SERIES[crop]["yield"], "agg_level_desc": "COUNTY", "state_alpha": state,
            "year__GE": str(years[0]), "year__LE": str(years[1]), "source_desc": "SURVEY", "format": "JSON"}


def parse_county(payload, series, min_years=3):
    """{county FIPS: mean yield}. '998' (other counties combined) and withheld values are skipped."""
    if "error" in payload:
        return {}
    values = {}
    for row in payload.get("data", []):
        if row.get("short_desc") != series:
            raise ValueError("The NASS response series does not match the request.")
        county = str(row.get("county_code", "")).zfill(3)
        raw = str(row.get("Value", "")).strip()
        if county in ("998", "999", "000") or raw.startswith("("):
            continue
        fips = str(row["state_fips_code"]).zfill(2) + county
        values.setdefault(fips, {})[int(row["year"])] = float(raw.replace(",", ""))
    return {f: sum(v.values()) / len(v) for f, v in values.items() if len(v) >= min_years}


def centroids():
    with ASSET_CENTROIDS.open(encoding="utf-8") as stream:
        return {r["fips"]: (float(r["longitude"]), float(r["latitude"])) for r in csv.DictReader(stream)}


def cell_of(lon, lat, cells, half):
    for c in cells:
        if abs(lon - c["longitude"]) <= half and abs(lat - c["latitude"]) <= half:
            return c["cell_id"]
    return None


def design(row, prefix):
    t, tx = row[f"{prefix}_t_mean_c"], row[f"{prefix}_tmax_jun_jul_c"]
    base = [row[f"{prefix}_{f}"] for f in FEATURES]
    return None if any(v is None for v in base) else base + [t * t, tx * tx]


NAMES = FEATURES + ["t_mean_c^2", "tmax_jun_jul_c^2"]


def fit_ridge(X, y, l2=1.0):
    n, k = len(X), len(X[0])
    means = [sum(r[j] for r in X) / n for j in range(k)]
    sds = [max(1e-9, math.sqrt(sum((r[j] - means[j]) ** 2 for r in X) / n)) for j in range(k)]
    Z = [[1.0] + [(r[j] - means[j]) / sds[j] for j in range(k)] for r in X]
    m = k + 1
    A = [[sum(Z[i][a] * Z[i][b] for i in range(n)) + (l2 if a == b and a > 0 else 0.0) for b in range(m)] for a in range(m)]
    rhs = [sum(Z[i][a] * y[i] for i in range(n)) for a in range(m)]
    for col in range(m):  # Gauss-Jordan
        pivot = max(range(col, m), key=lambda r: abs(A[r][col]))
        A[col], A[pivot], rhs[col], rhs[pivot] = A[pivot], A[col], rhs[pivot], rhs[col]
        d = A[col][col] or 1e-12
        A[col] = [v / d for v in A[col]]; rhs[col] /= d
        for r in range(m):
            if r != col and A[r][col]:
                f = A[r][col]
                A[r] = [a - f * b for a, b in zip(A[r], A[col])]; rhs[r] -= f * rhs[col]
    return {"beta": rhs, "means": means, "sds": sds}


def predict_one(model, x):
    return model["beta"][0] + sum(b * (v - m) / s for b, v, m, s in zip(model["beta"][1:], x, model["means"], model["sds"]))


def spatial_cv(samples, l2):
    blocks = sorted({s["block"] for s in samples})
    preds, obs = [], []
    for b in blocks:
        train = [s for s in samples if s["block"] != b]
        test = [s for s in samples if s["block"] == b]
        if len(train) < MIN_CELLS - 2:
            continue
        model = fit_ridge([s["x"] for s in train], [s["y"] for s in train], l2)
        for s in test:
            preds.append(predict_one(model, s["x"])); obs.append(s["y"])
    if len(obs) < 3:
        return None
    mean = sum(obs) / len(obs)
    sse = sum((p - o) ** 2 for p, o in zip(preds, obs))
    sst = sum((o - mean) ** 2 for o in obs) or 1e-9
    return {"r2": 1 - sse / sst, "rmse": math.sqrt(sse / len(obs)), "rmse_mean_only": math.sqrt(sst / len(obs)), "n": len(obs)}


def latest_corridor_cells(workspace):
    for folder in sorted((Path(workspace) / "outputs").glob("corridor_*"), reverse=True):
        path = folder / "corridor_cells.csv"
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        out = []
        for r in rows:
            row = {"cell_id": r["cell_id"], "block": r["block"]}
            for k, v in r.items():
                if k.startswith(("baseline_", "future_")) or k in ("longitude", "latitude"):
                    row[k] = float(v) if v not in ("", "None") else None
            out.append(row)
        usable = [r for r in out if r["longitude"] is not None and r.get("baseline_t_mean_c") is not None]
        if len(usable) >= MIN_CELLS:
            return folder, usable
    return None, []


def build(workspace, cells, online=False, key=None, years=YEARS, l2=1.0, crops=CROPS, half=0.5):
    """Pure computation: cells + NASS cache → model metrics and cell × crop multipliers."""
    key = key if key is not None else os.environ.get("FIELDSHIFT_NASS_KEY")
    cents = centroids()
    states = sorted({geo.FIPS.get(f[:2]) for f, (lon, lat) in cents.items() if cell_of(lon, lat, cells, half)} - {None})
    models, changes, problems, provenance = {}, [], [], []
    for crop in crops:
        series = economics.NASS_SERIES[crop]["yield"]
        by_cell = {}
        for state in states:
            try:
                payload, receipt = economics.nass_fetch(workspace, county_args(crop, state, years), key, online, "NASS county yield")
            except (ValueError, OSError) as error:
                problems.append(f"{crop}/{state}: {error}")
                continue
            provenance.append(receipt)
            for fips, value in parse_county(payload, series).items():
                if fips not in cents:
                    continue
                cell = cell_of(*cents[fips], cells, half)
                if cell:
                    by_cell.setdefault(cell, []).append(value)
        samples = []
        for c in cells:
            x = design(c, "baseline")
            if c["cell_id"] in by_cell and x:
                samples.append({"cell_id": c["cell_id"], "block": c["block"], "x": x,
                                "y": sum(by_cell[c["cell_id"]]) / len(by_cell[c["cell_id"]]), "counties": len(by_cell[c["cell_id"]])})
        if len(samples) < MIN_CELLS:
            models[crop] = {"status": "insufficient_data", "cells": len(samples),
                            "reason": f"Cells with NASS county yields {len(samples)} < {MIN_CELLS}"}
            continue
        model = fit_ridge([s["x"] for s in samples], [s["y"] for s in samples], l2)
        cv = spatial_cv(samples, l2)
        lo = [min(s["x"][j] for s in samples) for j in range(len(NAMES))]
        hi = [max(s["x"][j] for s in samples) for j in range(len(NAMES))]
        usable = cv is not None and cv["r2"] >= 0.2
        models[crop] = {"status": "usable" if usable else "weak", "cells": len(samples),
                        "counties": sum(s["counties"] for s in samples), "cv": cv, "features": NAMES, "l2": l2,
                        "observed_mean_bu_acre": sum(s["y"] for s in samples) / len(samples)}
        observed = {s["cell_id"]: s for s in samples}
        for c in cells:
            xb, xf = design(c, "baseline"), design(c, "future")
            if not xb or not xf:
                continue
            pb, pf = predict_one(model, xb), predict_one(model, xf)
            span = [h - l or 1e-9 for l, h in zip(lo, hi)]
            extrap = any(v < l - 0.1 * s or v > h + 0.1 * s for v, l, h, s in zip(xf, lo, hi, span))
            mult = None if pb <= 0 else max(CLIP[0], min(CLIP[1], pf / pb))
            changes.append({"cell_id": c["cell_id"], "crop": crop, "model_status": models[crop]["status"],
                            "observed_yield_bu_acre": round(observed[c["cell_id"]]["y"], 2) if c["cell_id"] in observed else None,
                            "predicted_baseline_bu_acre": round(pb, 2), "predicted_future_bu_acre": round(pf, 2),
                            "yield_multiplier": round(mult, 4) if mult is not None else None,
                            "extrapolation": int(extrap)})
    return {"models": models, "changes": changes, "problems": problems, "states": states, "provenance": provenance,
            "years": list(years)}


def run(workspace, online=False, key=None):
    workspace = Path(workspace).resolve()
    corridor_folder, cells = latest_corridor_cells(workspace)
    if not cells:
        raise ValueError("No corridor cell output, or climate features missing. First run: python3 -m fieldshift_data corridor --offline (or --online)")
    result = build(workspace, cells, online, key)
    if not result["provenance"]:
        raise ValueError("No NASS county yields could be retrieved; the model was not built (nothing written). "
                         "Set the key and run online: export FIELDSHIFT_NASS_KEY=yourkey ; "
                         "python3 -m fieldshift_data yield-model --online. First error: " + (result["problems"][0] if result["problems"] else "—"))
    output = workspace / "outputs" / ("yield_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    columns = ["cell_id", "crop", "model_status", "observed_yield_bu_acre", "predicted_baseline_bu_acre",
               "predicted_future_bu_acre", "yield_multiplier", "extrapolation"]
    with (output / "yield_change_cells.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(result["changes"])
    report = {k: result[k] for k in ("models", "problems", "states", "years")}
    report["corridor_output"] = corridor_folder.name
    report["nass_requests"] = len(result["provenance"])
    report["method"] = __doc__
    write_json(output / "yield_model.json", report)
    lines = ["# Climate-to-yield model (C/D)", "",
             f"Corridor output: `{corridor_folder.name}` · states: {', '.join(result['states'])} · NASS county yields {YEARS[0]}–{YEARS[1]}", "",
             "| Crop | Status | Cells | Counties | CV R² | RMSE (bu/acre) | Mean-only RMSE |", "|---|---|---|---|---|---|---|"]
    for crop, m in result["models"].items():
        cv = m.get("cv") or {}
        lines.append(f"| {crop} | {m['status']} | {m['cells']} | {m.get('counties', '—')} | "
                     f"{cv.get('r2', float('nan')):.2f} | {cv.get('rmse', float('nan')):.1f} | {cv.get('rmse_mean_only', float('nan')):.1f} |"
                     if cv else f"| {crop} | {m['status']} | {m['cells']} | — | — | — | {m.get('reason', '')} |")
    lines += ["", "Multiplier = model(2040–2049 climate) / model(2015–2024 climate), clipped to [0.5, 1.5]. "
              "`extrapolation=1`: future climate outside the training range; treat that cell's multiplier with caution.",
              "Multipliers of crops with status 'weak' are not used by goal (spatial validation R² < 0.2).", ""]
    if result["problems"]:
        lines += ["## Eksikler", ""] + [f"- {p}" for p in result["problems"][:30]]
    (output / "YIELD_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output, report


def latest_multipliers(workspace):
    """For goal: {(cell_id, crop): multiplier}, only from 'usable' models and cells without extrapolation."""
    for folder in sorted((Path(workspace) / "outputs").glob("yield_*"), reverse=True):
        path = folder / "yield_change_cells.csv"
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as stream:
            rows = [r for r in csv.DictReader(stream) if r.get("cell_id") and r.get("crop")]
        if not rows:
            continue
        table = {(r["cell_id"], r["crop"]): float(r["yield_multiplier"]) for r in rows
                 if r.get("model_status") == "usable" and r.get("yield_multiplier") not in (None, "", "None")
                 and r.get("extrapolation") == "0"}
        return folder.name, table, rows
    return None, {}, []
