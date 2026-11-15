"""Observed annual crop labels and sequences, linked only at valid scales."""

from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from uuid import uuid4

from .catalog import source_directory
from .cropland_source import WHEAT_CLASSES, cached_json, parse_service, parse_classes, parse_raster, samples
from .download import validate_cache
from .napeshm import prepare
from . import regional
from .tables import digest, numeric, read_zip_csv, write_csv, write_json


def validate_config(config):
    sites = config.get("sites")
    if not isinstance(sites, list) or not 1 <= len(sites) <= 5 or any(not isinstance(s, str) or not s for s in sites) or len(set(sites)) != len(sites):
        raise ValueError("1–5 distinct NAPESHM site codes are required.")
    years = config.get("years")
    if not isinstance(years, list) or len(years) != 2 or any(type(y) is not int for y in years) or not 2008 <= years[0] <= years[1] <= 2023 or years[1] - years[0] > 15:
        raise ValueError("At most 16 years within 2008–2023 are supported for one 30 m crop series.")
    if type(config.get("grid_side")) is not int or config["grid_side"] not in (1, 3, 5):
        raise ValueError("The point grid side must be 1, 3 or 5.")
    step = config.get("step_degrees")
    if type(step) not in (int, float) or not math.isfinite(step) or not .001 <= step <= .05:
        raise ValueError("Point spacing must be .001–.05 degrees.")


def grid(site, side, step):
    lon, lat = numeric(site["site_longitude"]), numeric(site["site_latitude"])
    if lon is None or lat is None or not -125 <= lon <= -66 or not 24 <= lat <= 50:
        raise ValueError("This CDL pilot needs valid site coordinates within the contiguous US.")
    half = side // 2
    return [{"sitecode": site["sitecode"], "point_id": f"{site['sitecode']}:r{r}:c{c}",
             "row": r, "column": c, "is_center": r == half and c == half,
             "longitude": round(lon + (c - half) * step, 8), "latitude": round(lat + (r - half) * step, 8)}
            for r in range(side) for c in range(side)]


def histories(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["point_id"]].append(row)
    sequences, transitions = [], []
    for point, records in sorted(groups.items()):
        records.sort(key=lambda r: r["year"])
        if len({r["year"] for r in records}) != len(records):
            raise ValueError("Duplicate point/year key.")
        sequences.append({"sitecode": records[0]["sitecode"], "point_id": point,
                          "first_year": records[0]["year"], "last_year": records[-1]["year"],
                          "complete": all(r["cdl_code"] is not None for r in records) and records[-1]["year"] - records[0]["year"] + 1 == len(records),
                          "classified_years": sum(r["cdl_code"] is not None for r in records),
                          "wheat_years": sum(r["wheat_present"] is True for r in records),
                          "code_sequence": " → ".join(str(r["cdl_code"]) if r["cdl_code"] is not None else "?" for r in records),
                          "class_sequence": " → ".join(r["class_name"] or "missing" for r in records)})
        for a, b in zip(records, records[1:]):
            if b["year"] == a["year"] + 1 and a["cdl_code"] is not None and b["cdl_code"] is not None:
                transitions.append({"sitecode": a["sitecode"], "point_id": point,
                                    "from_year": a["year"], "to_year": b["year"],
                                    "from_code": a["cdl_code"], "to_code": b["cdl_code"],
                                    "from_class": a["class_name"], "to_class": b["class_name"]})
    return sequences, transitions


def run(workspace, config_path, regional_config_path, online=False):
    workspace = Path(workspace).resolve()
    config_path, regional_config_path = Path(config_path), Path(regional_config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    climate_config = json.loads(regional_config_path.read_text(encoding="utf-8"))
    regional.validate_config(climate_config)
    if not set(config["sites"]) <= set(climate_config["sites"]):
        raise ValueError("Every CDL site must be in the regional climate configuration.")
    soil_provenance = validate_cache(workspace, "napeshm")
    tables = read_zip_csv(source_directory(workspace, "napeshm") / "NAPESHM_public_dataset_06032024.zip")
    processed, _ = prepare(tables)
    sites = {r["sitecode"]: r for r in tables["sites"].rows}
    points_by_site = {}
    for site in config["sites"]:
        if site not in sites:
            raise ValueError(f"NAPESHM site not found: {site}")
        points_by_site[site] = grid(sites[site], config["grid_side"], config["step_degrees"])
    provenance = []
    _, receipt = cached_json(workspace, "", {}, parse_service, online)
    provenance.append(receipt)
    classes, receipt = cached_json(workspace, "rasterAttributeTable", {}, parse_classes, online)
    provenance.append(receipt)
    observations = []
    for year in range(config["years"][0], config["years"][1] + 1):
        raster, receipt = cached_json(workspace, "query", {"where": f"Year = {year} AND Category = 1",
                                      "outFields": "OBJECTID,Name,Year", "returnGeometry": "false"},
                                      lambda payload: parse_raster(payload, year), online)
        provenance.append(receipt)
        for site, points in points_by_site.items():
            print(f"CDL: {site}, {year}, {len(points)} points", flush=True)
            rows, receipt = samples(workspace, points, year, raster["OBJECTID"], online)
            provenance.append(receipt)
            for row in rows:
                code = row["cdl_code"]
                if code is not None and not classes.get(code):
                    raise ValueError(f"CDL code {code} has no definition; no negative label was created.")
                observations.append({**row, "class_name": classes.get(code),
                                     "wheat_present": code in WHEAT_CLASSES if code is not None else None,
                                     "wheat_double_crop": code in WHEAT_CLASSES and code not in (22, 23, 24) if code is not None else None,
                                     "context_id": site, "soil_assignment": "site_context_only"})
    sequences, transitions = histories(observations)
    _, climate_report = regional.run(workspace, regional_config_path, online)
    climate_context = [{"context_id": s["sitecode"], "scenario": climate_config["scenario"],
                        "model": "ensemble", "baseline_first": climate_config["baseline"][0],
                        "baseline_last": climate_config["baseline"][1], "future_first": climate_config["future"][0],
                        "future_last": climate_config["future"][1], **m}
                       for s in climate_report["sites"] if s["sitecode"] in config["sites"] for m in s["monthly_change"]]
    soil_context = [{"context_id": r["sitecode"], **r} for r in processed["soil_indicators"] if r["sitecode"] in config["sites"]]
    coverage = []
    for site in config["sites"]:
        for year in range(config["years"][0], config["years"][1] + 1):
            records = [r for r in observations if r["sitecode"] == site and r["year"] == year]
            count = sum(r["cdl_code"] is not None for r in records)
            wheat = sum(r["wheat_present"] is True for r in records)
            coverage.append({"sitecode": site, "year": year, "requested_points": len(records), "classified_points": count,
                             "unknown_points": len(records) - count, "wheat_points": wheat,
                             "wheat_fraction_of_classified_samples": wheat / count if count else None})
    output = workspace / "outputs" / ("cropland_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    write_csv(output / "crop_observations.csv", observations)
    write_csv(output / "observed_sequences.csv", sequences)
    write_csv(output / "observed_transitions.csv", transitions,
              ["sitecode", "point_id", "from_year", "to_year", "from_code", "to_code", "from_class", "to_class"])
    write_csv(output / "sample_coverage.csv", coverage)
    write_csv(output / "climate_context.csv", climate_context)
    write_json(output / "regional_context.json", climate_report)
    write_csv(output / "soil_context.csv", soil_context)
    write_csv(output / "class_dictionary.csv", [{"cdl_code": code, "class_name": label,
                                                 "wheat_present": code in WHEAT_CLASSES if label and code != 0 else None}
                                                for code, label in sorted(classes.items())])
    write_json(output / "crop_samples.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
         "properties": {k: v for k, v in r.items() if k not in ("longitude", "latitude")}} for r in observations]})
    report = {"method": "observed_cdl_point_sequences_v1", "config": config, "config_sha256": digest(config_path),
              "source": "USDA NASS Cropland Data Layer (CDL), CroplandCROS", "provenance": provenance,
              "soil_provenance": soil_provenance, "regional_config_sha256": digest(regional_config_path),
              "climate_report_file": "regional_context.json",
              "climate_provenance": climate_report["provenance"], "observations": len(observations),
              "points": len(sequences), "classified_observations": sum(r["cdl_code"] is not None for r in observations),
              "wheat_observations": sum(r["wheat_present"] is True for r in observations),
              "adjacent_year_transitions": len(transitions), "spatial_context_groups": len(config["sites"]),
              "soil_plot_count": len({r["euid"] for r in soil_context}), "soil_indicator_rows": len(soil_context),
              "model_ready": False, "optimal_rotation_calculated": False,
              "limitations": ["CDL is a satellite classification; at a point it is not a farmer declaration or field truth.",
                              "Absence of wheat does not mean wheat cannot grow; it may be another crop or land use.",
                              "Shares of sample points are not shares of hectares or of regional planted area.",
                              "A point sequence is the observed history of crop classes; it does not prove that the cycle repeats or is optimal.",
                              "Soil and climate contexts are at the central-site level; they are not independent measurements for the surrounding points.",
                              "Soil indicators are kept separate; they are not assigned to surrounding points as measured targets.",
                              "Double-crop codes are kept within the same year; they are not split into one crop or two years.",
                              "The CDL year of winter wheat is the harvest year; it is not confused with the autumn sowing year.",
                              "Two sites do not validate spatial generalisation or future suitability; Canada/Mexico are out of scope."]}
    write_json(output / "cropland.json", report)
    lines = ["# FieldShift real crop distribution and crop histories", "",
             f"Period: {config['years']}; sites: {', '.join(config['sites'])}; points: {len(sequences)}; point-years: {len(observations)}.", "",
             f"Classifications with wheat: {report['wheat_observations']}; consecutive-year transitions: {len(transitions)}.", "",
             "| Site | Year | Classified points | Points with wheat |", "|---|---:|---:|---:|"]
    lines.extend(f"| {r['sitecode']} | {r['year']} | {r['classified_points']} | {r['wheat_points']} |" for r in coverage)
    lines.extend(["", "## History of the central points", ""])
    center_ids = {p["point_id"] for points in points_by_site.values() for p in points if p["is_center"]}
    lines.extend(f"- {r['sitecode']}: {r['class_sequence']}" for r in sequences if r["point_id"] in center_ids)
    lines.extend(["", "## Joining and interpretation", "",
                  f"Soil: {report['soil_plot_count']} separate observations, {len(soil_context)} indicator rows. Climate: {len(climate_context)} site/month contexts.", "",
                  "Crop points refer to the site context by context_id; soil measurements are not duplicated per point-year.", "",
                  *["- " + item for item in report["limitations"]], "",
                  "Source: https://www.nass.usda.gov/Research_and_Science/Cropland/sarsfaqs2.php",
                  "Service: https://pdi.scinet.usda.gov/image/rest/services/CDL_WM/ImageServer", ""])
    (output / "CROPLAND_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return output, report
