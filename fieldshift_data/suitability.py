"""Components A + D: wheat climate-suitability model and the future shift (migration) corridor.

Training: USDA CDL wheat presence in grid cells (label) ~ NASA NEX-GDDP model reference climate (features).
Validation: spatial block cross-validation (neighbouring cells stay in the same fold).
Projection: the same model applied to the future-period climate of the same scenario.
Reference and future come from the same projection source; observations and model output are never mixed.
Only mean-based features are used: threshold-exceedance counts on ensemble-mean days are biased.
"""

from collections import defaultdict
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
from statistics import fmean
from uuid import uuid4

from . import climate
from .cropland_source import WHEAT_CLASSES, cached_json, parse_classes, parse_raster, parse_service, samples
from .tables import digest, write_csv, write_json

FEATURES = ["t_mean_c", "gdd0_annual", "tmax_jun_jul_c", "prec_annual_mm", "prec_oct_jun_mm"]
FEATURE_LABELS = {"t_mean_c": "annual mean temperature (°C)", "gdd0_annual": "annual growing degree days, base 0°C",
                  "tmax_jun_jul_c": "June–July mean daily maximum temperature (°C)",
                  "prec_annual_mm": "annual precipitation (mm)", "prec_oct_jun_mm": "October–June precipitation (mm, winter-wheat season)"}


def is_cropland(code):
    return code is not None and (1 <= code <= 61 or 66 <= code <= 80 or 204 <= code <= 254)


def validate_config(config):
    box = config.get("bbox", {})
    if not all(isinstance(box.get(k), (int, float)) for k in ("west", "east", "south", "north")):
        raise ValueError("bbox west/east/south/north must be numbers.")
    if not (-125 <= box["west"] < box["east"] <= -66 and 24 <= box["south"] < box["north"] <= 50):
        raise ValueError("CDL covers only the contiguous US; the bbox must lie within it.")
    for key in ("cell_step_degrees", "point_step_degrees", "l2"):
        if not isinstance(config.get(key), (int, float)) or config[key] <= 0:
            raise ValueError(f"{key} must be a positive number.")
    for key in ("points_per_cell_side", "block_size_cells", "min_cells_for_training", "min_positive_cells", "min_negative_cells"):
        if type(config.get(key)) is not int or config[key] < 1:
            raise ValueError(f"{key} must be a positive integer.")
    for key in ("baseline", "future"):
        first, last = config[key]
        if not 2015 <= first <= last <= 2100 or (last - first + 1) % 5:
            raise ValueError("Periods must lie within 2015–2100 and have a length that is a multiple of 5 years.")
    first, last = config["cdl_years"]
    if not 2008 <= first <= last <= 2023:
        raise ValueError("CDL years must be between 2008 and 2023.")


def cells_from_bbox(config):
    box, step = config["bbox"], config["cell_step_degrees"]
    cells = []
    nx = int(round((box["east"] - box["west"]) / step))
    ny = int(round((box["north"] - box["south"]) / step))
    for j in range(ny):
        for i in range(nx):
            lon = box["west"] + (i + 0.5) * step
            lat = box["south"] + (j + 0.5) * step
            cells.append({"cell_id": f"c{j:02d}_{i:02d}", "row": j, "col": i,
                          "longitude": round(lon, 6), "latitude": round(lat, 6),
                          "block": f"b{j // config['block_size_cells']}_{i // config['block_size_cells']}"})
    return cells


def points_for_cell(cell, side, step):
    half = (side - 1) / 2
    return [{"cell_id": cell["cell_id"], "point_id": f"{cell['cell_id']}:p{r}{c}",
             "longitude": round(cell["longitude"] + (c - half) * step, 8),
             "latitude": round(cell["latitude"] + (r - half) * step, 8)}
            for r in range(side) for c in range(side)]


def features_from_daily(rows):
    """Mean-based features; each feature needs at least 90% of the relevant days."""
    def mean_of(values, expected):
        present = [v for v in values if v is not None]
        return fmean(present) if expected and len(present) >= 0.9 * expected else None
    all_t = [r["T2M"] for r in rows]
    jj = [r["T2M_MAX"] for r in rows if r["date"][5:7] in ("06", "07")]
    pr = [r["PRECTOTCORR"] for r in rows]
    oj = [r["PRECTOTCORR"] for r in rows if r["date"][5:7] not in ("07", "08", "09")]
    t_mean = mean_of(all_t, len(all_t))
    gdd = mean_of([None if t is None else max(t, 0.0) for t in all_t], len(all_t))
    p_mean = mean_of(pr, len(pr))
    oj_mean = mean_of(oj, len(oj))
    return {"t_mean_c": t_mean, "gdd0_annual": None if gdd is None else gdd * 365.25,
            "tmax_jun_jul_c": mean_of(jj, len(jj)),
            "prec_annual_mm": None if p_mean is None else p_mean * 365.25,
            "prec_oct_jun_mm": None if oj_mean is None else oj_mean * 273.0}


def period_rows(fetch, first, last):
    rows = []
    for start in range(first, last + 1, 5):
        rows.extend(fetch(date(start, 1, 1), date(min(start + 4, last), 12, 31)))
    return rows


# --- Logistic regression (standard library) ---

def standardize(X):
    means = [fmean(col) for col in zip(*X)]
    sds = [math.sqrt(fmean([(v - m) ** 2 for v in col])) or 1.0 for col, m in zip(zip(*X), means)]
    return means, sds


def transform(X, means, sds):
    return [[(v - m) / s for v, m, s in zip(row, means, sds)] for row in X]


def sigmoid(z):
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def fit_logistic(X, y, l2=0.1, iterations=3000, rate=0.3):
    means, sds = standardize(X)
    Z = transform(X, means, sds)
    n, k = len(Z), len(Z[0])
    w, b = [0.0] * k, 0.0
    for _ in range(iterations):
        grad_w, grad_b = [0.0] * k, 0.0
        for row, target in zip(Z, y):
            error = sigmoid(b + sum(wi * xi for wi, xi in zip(w, row))) - target
            grad_b += error
            for j in range(k):
                grad_w[j] += error * row[j]
        b -= rate * grad_b / n
        w = [wi - rate * (gw / n + l2 * wi) for wi, gw in zip(w, grad_w)]
    return {"weights": w, "intercept": b, "means": means, "sds": sds}


def predict(model, X):
    Z = transform(X, model["means"], model["sds"])
    return [sigmoid(model["intercept"] + sum(w * x for w, x in zip(model["weights"], row))) for row in Z]


def auc(scores, labels):
    pairs = sorted(zip(scores, labels))
    pos = sum(labels)
    neg = len(labels) - pos
    if not pos or not neg:
        return None
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        average_rank = (i + 1 + j) / 2
        rank_sum += average_rank * sum(label for _, label in pairs[i:j])
        i = j
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def spatial_cv(samples_, l2):
    """Each block is the test fold once; cells in the test block are never used for training."""
    blocks = sorted({s["block"] for s in samples_})
    scores, labels, folds = [], [], 0
    for block in blocks:
        train = [s for s in samples_ if s["block"] != block]
        test = [s for s in samples_ if s["block"] == block]
        if len({s["label"] for s in train}) < 2 or not test:
            continue
        model = fit_logistic([s["x"] for s in train], [s["label"] for s in train], l2)
        scores.extend(predict(model, [s["x"] for s in test]))
        labels.extend(s["label"] for s in test)
        folds += 1
    brier = fmean([(p - y) ** 2 for p, y in zip(scores, labels)]) if scores else None
    prevalence = fmean(labels) if labels else None
    brier_null = fmean([(prevalence - y) ** 2 for y in labels]) if labels else None
    return {"folds": folds, "auc": auc(scores, labels), "brier": brier, "brier_prevalence_only": brier_null,
            "test_samples": len(labels)}


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def weighted_centroid(cells, key):
    weights = [(c[key], c) for c in cells if c.get(key) is not None]
    total = sum(w for w, _ in weights)
    if not total:
        return None
    return {"latitude": sum(w * c["latitude"] for w, c in weights) / total,
            "longitude": sum(w * c["longitude"] for w, c in weights) / total}


def analyse(cells, points, config):
    """cells: cells with features; points: cell_id, label (1 wheat, 0 cropland without wheat)."""
    by_cell = {c["cell_id"]: c for c in cells}
    usable = [p for p in points if p["label"] is not None and by_cell.get(p["cell_id"], {}).get("baseline_ok")]
    cell_labels = defaultdict(set)
    for p in usable:
        cell_labels[p["cell_id"]].add(p["label"])
    positive_cells = sum(1 in labels for labels in cell_labels.values())
    negative_cells = sum(0 in labels for labels in cell_labels.values())
    distinct_climates = len({tuple(round(by_cell[c]["baseline"][f], 3) for f in FEATURES) for c in cell_labels})
    readiness = {"cells_with_cropland": len(cell_labels), "distinct_climate_cells": distinct_climates,
                 "positive_cells": positive_cells, "negative_cells": negative_cells,
                 "required": {"cells": config["min_cells_for_training"], "positive": config["min_positive_cells"],
                              "negative": config["min_negative_cells"]}}
    reasons = []
    if distinct_climates < config["min_cells_for_training"]:
        reasons.append(f"Cells with distinct climate {distinct_climates} < {config['min_cells_for_training']}")
    if positive_cells < config["min_positive_cells"]:
        reasons.append(f"Cells with wheat {positive_cells} < {config['min_positive_cells']}")
    if negative_cells < config["min_negative_cells"]:
        reasons.append(f"Cropland cells without wheat {negative_cells} < {config['min_negative_cells']}")
    readiness["trained"] = not reasons
    readiness["reasons"] = reasons
    result = {"readiness": readiness, "model": None, "validation": None, "shift": None}
    if reasons:
        return result
    samples_ = [{"x": [by_cell[p["cell_id"]]["baseline"][f] for f in FEATURES], "label": p["label"],
                 "block": by_cell[p["cell_id"]]["block"]} for p in usable]
    result["validation"] = spatial_cv(samples_, config["l2"])
    model = fit_logistic([s["x"] for s in samples_], [s["label"] for s in samples_], config["l2"])
    result["model"] = {**model, "features": FEATURES, "training_samples": len(samples_)}
    for cell in cells:
        for period in ("baseline", "future"):
            ok = cell.get(f"{period}_ok")
            cell[f"suitability_{period}"] = predict(model, [[cell[period][f] for f in FEATURES]])[0] if ok else None
        b, f = cell["suitability_baseline"], cell["suitability_future"]
        cell["suitability_change"] = None if b is None or f is None else f - b
    c0, c1 = weighted_centroid(cells, "suitability_baseline"), weighted_centroid(cells, "suitability_future")
    if c0 and c1:
        threshold = config.get("suitable_threshold", 0.5)
        max_row = max((c.get("row") or 0) for c in cells)
        max_col = max((c.get("col") or 0) for c in cells)
        for cell in cells:
            for period in ("baseline", "future"):
                p = cell[f"suitability_{period}"]
                cell[f"suitable_{period}"] = None if p is None else int(p >= threshold)
        h0 = weighted_centroid([c for c in cells if c.get("suitable_baseline")], "suitable_baseline")
        h1 = weighted_centroid([c for c in cells if c.get("suitable_future")], "suitable_future")
        zone = None
        if h0 and h1:
            zone = {"threshold": threshold, "baseline_centroid": h0, "future_centroid": h1,
                    "distance_km": haversine_km(h0["latitude"], h0["longitude"], h1["latitude"], h1["longitude"]),
                    "bearing_deg": bearing_deg(h0["latitude"], h0["longitude"], h1["latitude"], h1["longitude"]),
                    "cells_baseline": sum(1 for c in cells if c.get("suitable_baseline")),
                    "cells_future": sum(1 for c in cells if c.get("suitable_future")),
                    "cells_gained": sum(1 for c in cells if c.get("suitable_future") == 1 and c.get("suitable_baseline") == 0),
                    "cells_lost": sum(1 for c in cells if c.get("suitable_future") == 0 and c.get("suitable_baseline") == 1),
                    "touches_box_edge": any(c.get("suitable_future") and c.get("row") is not None and c.get("col") is not None and (
                        c["row"] in (0, max_row) or c["col"] in (0, max_col)) for c in cells)}
        result["shift"] = {"baseline_centroid": c0, "future_centroid": c1,
                           "distance_km": haversine_km(c0["latitude"], c0["longitude"], c1["latitude"], c1["longitude"]),
                           "bearing_deg": bearing_deg(c0["latitude"], c0["longitude"], c1["latitude"], c1["longitude"]),
                           "suitable_zone": zone}
    return result


# --- Data acquisition ---

def corridor_data(workspace, config, online):
    """CDL labels and NASA climate features for the grid cells (cache or --online)."""
    cells = cells_from_bbox(config)
    provenance = []
    for number, cell in enumerate(cells, 1):
        print(f"NASA climate corridor: cell {number}/{len(cells)} ({cell['cell_id']})", flush=True)
        for period in ("baseline", "future"):
            first, last = config[period]
            fetch = lambda a, b, c=cell: climate.get_point(workspace, f"grid:{c['cell_id']}", c["latitude"], c["longitude"], a, b,
                                                           "projection", config["scenario"], online,
                                                           {"dataset": "corridor_grid", "cell_id": c["cell_id"]})[0]
            try:
                rows = period_rows(fetch, first, last)
            except (ValueError, OSError) as error:
                if not online:
                    raise ValueError(str(error)) from error
                cell[period] = {f: None for f in FEATURES}
                cell[f"{period}_ok"] = False
                cell[f"{period}_error"] = str(error)
                continue
            cell[period] = features_from_daily(rows)
            cell[f"{period}_ok"] = all(cell[period][f] is not None for f in FEATURES)
    points = [p for cell in cells for p in points_for_cell(cell, config["points_per_cell_side"], config["point_step_degrees"])]
    _, receipt = cached_json(workspace, "", {}, parse_service, online)
    provenance.append(receipt)
    classes, receipt = cached_json(workspace, "rasterAttributeTable", {}, parse_classes, online)
    provenance.append(receipt)
    history = defaultdict(list)
    for year in range(config["cdl_years"][0], config["cdl_years"][1] + 1):
        raster, receipt = cached_json(workspace, "query", {"where": f"Year = {year} AND Category = 1",
                                      "outFields": "OBJECTID,Name,Year", "returnGeometry": "false"},
                                      lambda payload, y=year: parse_raster(payload, y), online)
        provenance.append(receipt)
        for i in range(0, len(points), 100):
            chunk = points[i:i + 100]
            print(f"CDL corridor: {year}, points {i + 1}–{i + len(chunk)}", flush=True)
            rows, receipt = samples(workspace, chunk, year, raster["OBJECTID"], online)
            provenance.append(receipt)
            for row in rows:
                history[row["point_id"]].append(row["cdl_code"])
    for p in points:
        codes = history[p["point_id"]]
        p["cdl_years"] = f"{config['cdl_years'][0]}-{config['cdl_years'][1]}"
        p["cdl_sequence"] = " → ".join(classes.get(c) or "missing" if c is not None else "missing" for c in codes)
        crop_years = [c for c in codes if is_cropland(c)]
        p["cropland_years"] = len(crop_years)
        p["wheat_years"] = sum(c in WHEAT_CLASSES for c in crop_years)
        p["label"] = None if not crop_years else int(p["wheat_years"] > 0)
    return cells, points, provenance, "corridor_grid"


def load_pilot_observations(workspace):
    """Rebuilds the 0.6.0 CDL pilot points from the packaged cache (offline)."""
    import csv
    from . import cropland as cropland_module
    root = Path(__file__).resolve().parent.parent
    output, report = cropland_module.run(workspace, root / "config/cropland.json", root / "config/regional.json", False)
    with (output / "crop_observations.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row["cdl_code"] = int(row["cdl_code"]) if row["cdl_code"] else None
        row["year"] = int(row["year"])
        row["longitude"], row["latitude"] = float(row["longitude"]), float(row["latitude"])
    return rows, report, output


def pilot_data(workspace, config, preloaded=None):
    """Offline fallback: the two packaged NAPESHM sites and the 0.6.0 CDL points. Reported as insufficient for training."""
    observations, crop_report, _ = preloaded or load_pilot_observations(workspace)
    cells, points = [], []
    by_point = defaultdict(list)
    for row in observations:
        by_point[(row["sitecode"], row["point_id"])].append(row)
    for site in crop_report["config"]["sites"]:
        cell = {"cell_id": site, "row": 0, "col": 0, "block": site}
        centre = [r for r in observations if r["sitecode"] == site and r["is_center"] == "True"]
        cell["longitude"], cell["latitude"] = (centre[0]["longitude"], centre[0]["latitude"]) if centre else (None, None)
        for period in ("baseline", "future"):
            first, last = config[period]
            rows = period_rows(lambda a, b: climate.get(workspace, site, a, b, "projection", config["scenario"], False)[0], first, last)
            cell[period] = features_from_daily(rows)
            cell[f"{period}_ok"] = all(cell[period][f] is not None for f in FEATURES)
        cells.append(cell)
    for (site, point_id), rows in sorted(by_point.items()):
        crop_years = [r["cdl_code"] for r in rows if is_cropland(r["cdl_code"])]
        points.append({"cell_id": site, "point_id": point_id, "longitude": rows[0]["longitude"], "latitude": rows[0]["latitude"],
                       "cropland_years": len(crop_years), "wheat_years": sum(c in WHEAT_CLASSES for c in crop_years),
                       "label": None if not crop_years else int(any(c in WHEAT_CLASSES for c in crop_years))})
    return cells, points, crop_report.get("provenance", []), "pilot_sites_offline"


def run(workspace, config_path, online=False, mode="auto", preloaded=None):
    workspace = Path(workspace).resolve()
    config_path = Path(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    source_note = None
    if mode in ("auto", "corridor"):
        try:
            cells, points, provenance, source = corridor_data(workspace, config, online)
        except ValueError as error:
            if mode == "corridor":
                raise
            source_note = f"Corridor grid not in cache or could not be downloaded ({error}). Ran with the two packaged pilot sites."
            cells, points, provenance, source = pilot_data(workspace, config, preloaded)
    else:
        cells, points, provenance, source = pilot_data(workspace, config, preloaded)
    result = analyse(cells, points, config)
    for cell in cells:
        for period in ("baseline", "future"):
            cell.setdefault(f"suitability_{period}", None)
        cell.setdefault("suitability_change", None)
    output = workspace / "outputs" / ("corridor_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    cell_rows = [{"cell_id": c["cell_id"], "block": c["block"], "longitude": c["longitude"], "latitude": c["latitude"],
                  **{f"baseline_{f}": c["baseline"][f] for f in FEATURES}, **{f"future_{f}": c["future"][f] for f in FEATURES},
                  "cropland_points": sum(1 for p in points if p["cell_id"] == c["cell_id"] and p["label"] is not None),
                  "wheat_points": sum(1 for p in points if p["cell_id"] == c["cell_id"] and p["label"] == 1),
                  "suitability_baseline": c["suitability_baseline"], "suitability_future": c["suitability_future"],
                  "suitability_change": c["suitability_change"], "suitable_baseline": c.get("suitable_baseline"),
                  "suitable_future": c.get("suitable_future")} for c in cells]
    write_csv(output / "corridor_cells.csv", cell_rows)
    write_csv(output / "corridor_points.csv", points)
    half = config["cell_step_degrees"] / 2
    features = []
    for c in cells:
        if c["longitude"] is None:
            continue
        geometry = ({"type": "Polygon", "coordinates": [[[c["longitude"] - half, c["latitude"] - half], [c["longitude"] + half, c["latitude"] - half],
                                                          [c["longitude"] + half, c["latitude"] + half], [c["longitude"] - half, c["latitude"] + half],
                                                          [c["longitude"] - half, c["latitude"] - half]]]}
                    if source == "corridor_grid" else {"type": "Point", "coordinates": [c["longitude"], c["latitude"]]})
        features.append({"type": "Feature", "geometry": geometry,
                         "properties": {k: v for k, v in next(r for r in cell_rows if r["cell_id"] == c["cell_id"]).items()
                                        if k not in ("longitude", "latitude")}})
    if result["shift"]:
        s = result["shift"]
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
            [s["baseline_centroid"]["longitude"], s["baseline_centroid"]["latitude"]],
            [s["future_centroid"]["longitude"], s["future_centroid"]["latitude"]]]},
            "properties": {"kind": "wheat_suitability_centroid_shift", **{k: v for k, v in s.items() if k.endswith(("km", "deg"))}}})
    write_json(output / "corridor.geojson", {"type": "FeatureCollection", "features": features})
    report = {"method": "cdl_presence_logistic_spatial_block_cv_v1", "component": "A+D", "source": source,
              "source_note": source_note, "config": config, "config_sha256": digest(config_path),
              "features": FEATURE_LABELS, **result, "cells": len(cells), "points": len(points),
              "provenance_files": len(provenance),
              "limitations": ["Labels are the CDL satellite classification; a cropland point without wheat does not mean wheat cannot grow there — it may be an economic choice.",
                              "The model has no non-climate factors (soil, irrigation, markets); suitability means climatic similarity.",
                              "Reference and future come from the same NEX-GDDP ensemble; the ensemble mean smooths extremes.",
                              "The shift vector is the displacement of the suitability-weighted centroid, not a physical movement of wheat.",
                              "A shift beyond the box cannot be measured; if the corridor touches the box edge, the box should be widened."]}
    write_json(output / "corridor.json", report)
    lines = ["# FieldShift migration corridor (component A) and suitability model (component D)", "",
             f"Data source: {source}." + (f" {source_note}" if source_note else ""), "",
             f"Cells: {len(cells)}; CDL points: {len(points)}; scenario: {config['scenario']}; reference {config['baseline']} → future {config['future']}.", "",
             "## Model readiness", ""]
    r = result["readiness"]
    lines += [f"- Cells with cropland: {r['cells_with_cropland']} (distinct climate: {r['distinct_climate_cells']})",
              f"- Cells with wheat: {r['positive_cells']}; cropland cells without wheat: {r['negative_cells']}",
              f"- Trained: {'yes' if r['trained'] else 'no'}"]
    lines += [f"- Reason: {x}" for x in r["reasons"]]
    if result["validation"]:
        v = result["validation"]
        lines += ["", "## Spatial block cross-validation", "",
                  f"- Folds: {v['folds']}; test samples: {v['test_samples']}",
                  f"- AUC: {v['auc']:.3f} (0.5 = random)" if v["auc"] is not None else "- AUC: could not be computed",
                  f"- Brier: {v['brier']:.4f}; prevalence-only Brier: {v['brier_prevalence_only']:.4f}" if v["brier"] is not None else "- Brier: could not be computed"]
    if result["shift"]:
        s = result["shift"]
        lines += ["", "## Shift of the suitability centre", "",
                  f"- Referans merkez: {s['baseline_centroid']['latitude']:.3f}, {s['baseline_centroid']['longitude']:.3f}",
                  f"- Gelecek merkez: {s['future_centroid']['latitude']:.3f}, {s['future_centroid']['longitude']:.3f}",
                  f"- Shift: {s['distance_km']:.1f} km, bearing {s['bearing_deg']:.0f}° (0° north, 90° east)"]
        z = s.get("suitable_zone")
        if z:
            lines += ["", f"**Suitable zone (probability ≥ {z['threshold']}):** {z['cells_baseline']} cells → {z['cells_future']} cells; "
                          f"gained {z['cells_gained']}, lost {z['cells_lost']}. The zone centre moves {z['distance_km']:.1f} km at a bearing of {z['bearing_deg']:.0f}°. "
                          "This is the estimate of the most suitable region wheat will migrate to (Preparation.md)."]
            if z["touches_box_edge"]:
                lines.append("**Warning:** the future suitable zone touches the edge of the box; the shift may continue beyond it. Widen `bbox`.")
    lines += ["", "## Cell climate: reference → future", "", "| Cell | Mean temp. (°C) | GDD0 | Jun–Jul Tmax (°C) | Oct–Jun precip. (mm) |", "|---|---|---|---|---|"]
    fmt = lambda v, d=1: "missing" if v is None else f"{v:.{d}f}"
    for c in cells[:60]:
        lines.append(f"| {c['cell_id']} | {fmt(c['baseline']['t_mean_c'])} → {fmt(c['future']['t_mean_c'])} | "
                     f"{fmt(c['baseline']['gdd0_annual'], 0)} → {fmt(c['future']['gdd0_annual'], 0)} | "
                     f"{fmt(c['baseline']['tmax_jun_jul_c'])} → {fmt(c['future']['tmax_jun_jul_c'])} | "
                     f"{fmt(c['baseline']['prec_oct_jun_mm'], 0)} → {fmt(c['future']['prec_oct_jun_mm'], 0)} |")
    lines += ["", "## Limits of interpretation", "", *["- " + x for x in report["limitations"]], ""]
    (output / "CORRIDOR_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return output, report
