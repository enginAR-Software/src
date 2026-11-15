"""Same-model, same-scenario climate differences at documented study sites.

No inferred crop thresholds, suitability score, soil response or migration route.
"""

from collections import defaultdict
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
from statistics import fmean
from uuid import uuid4

from . import climate
from .tables import digest, write_csv, write_json


def validate_config(config):
    sites = config.get("sites", [])
    if not isinstance(sites, list) or not 1 <= len(sites) <= 20 or any(
            not isinstance(s, str) or not s for s in sites) or len(set(sites)) != len(sites):
        raise ValueError("1–20 distinct NAPESHM site codes are required.")
    if config.get("scenario") not in ("ssp126", "ssp245", "ssp370"):
        raise ValueError("A supported SSP scenario is required.")
    for key in ("baseline", "future"):
        years = config.get(key)
        if not isinstance(years, list) or len(years) != 2 or any(type(y) is not int for y in years):
            raise ValueError("Periods must be [first_year, last_year].")
        if not 2015 <= years[0] <= years[1] <= 2100 or not 5 <= years[1] - years[0] + 1 <= 30:
            raise ValueError("Periods of 5–30 years within 2015–2100 are required.")
    baseline, future = config["baseline"], config["future"]
    if baseline[1] >= future[0] or baseline[1] - baseline[0] != future[1] - future[0]:
        raise ValueError("Separate reference and future periods of equal length are required.")


def period_statistics(rows, first, last):
    """Equal weight per year; every expected day must exist, missing stays null."""
    expected = {d.isoformat() for d in climate.dates(date(first, 1, 1), date(last, 12, 31))}
    if len(rows) != len(expected) or {r["date"] for r in rows} != expected:
        raise ValueError("Period days missing, duplicated or out of range.")
    grouped = defaultdict(list)
    for row in rows:
        for parameter in ("T2M", "PRECTOTCORR"):
            value = row[parameter]
            if value is not None and (not math.isfinite(value) or parameter == "PRECTOTCORR" and value < 0):
                raise ValueError("Invalid numeric climate value.")
        grouped[row["date"][:7]].append(row)
    monthly_years = []
    for month, records in sorted(grouped.items()):
        temperatures = [r["T2M"] for r in records if r["T2M"] is not None]
        precipitation = [r["PRECTOTCORR"] for r in records if r["PRECTOTCORR"] is not None]
        monthly_years.append({"year": int(month[:4]), "month": int(month[5:]),
                              "expected_days": len(records), "temperature_days": len(temperatures),
                              "precipitation_days": len(precipitation),
                              "mean_temperature_c": fmean(temperatures) if len(temperatures) == len(records) else None,
                              "precipitation_sum_mm": sum(precipitation) if len(precipitation) == len(records) else None})
    annual = []
    for year in range(first, last + 1):
        records = [r for r in rows if r["date"].startswith(str(year))]
        temps = [r["T2M"] for r in records if r["T2M"] is not None]
        rain = [r["PRECTOTCORR"] for r in records if r["PRECTOTCORR"] is not None]
        annual.append({"year": year, "expected_days": len(records), "temperature_days": len(temps),
                       "precipitation_days": len(rain),
                       "mean_temperature_c": fmean(temps) if len(temps) == len(records) else None,
                       "precipitation_sum_mm": sum(rain) if len(rain) == len(records) else None})
    def complete_mean(values):
        return fmean(values) if all(v is not None for v in values) else None
    months = [{"month": month,
               "mean_temperature_c": complete_mean([r["mean_temperature_c"] for r in monthly_years if r["month"] == month]),
               "mean_precipitation_mm": complete_mean([r["precipitation_sum_mm"] for r in monthly_years if r["month"] == month])}
              for month in range(1, 13)]
    return {"first_year": first, "last_year": last, "years": last - first + 1,
            "expected_days": len(rows),
            "temperature_days": sum(r["temperature_days"] for r in annual),
            "precipitation_days": sum(r["precipitation_days"] for r in annual),
            "complete_temperature_years": sum(r["mean_temperature_c"] is not None for r in annual),
            "complete_precipitation_years": sum(r["precipitation_sum_mm"] is not None for r in annual),
            "mean_temperature_c": complete_mean([r["mean_temperature_c"] for r in annual]),
            "mean_annual_precipitation_mm": complete_mean([r["precipitation_sum_mm"] for r in annual]),
            "annual": annual, "monthly_years": monthly_years, "months": months}


def compare(baseline, future):
    def delta(a, b):
        return b - a if a is not None and b is not None else None
    rain_a, rain_b = baseline["mean_annual_precipitation_mm"], future["mean_annual_precipitation_mm"]
    rain_delta = delta(rain_a, rain_b)
    annual = {"temperature_delta_c": delta(baseline["mean_temperature_c"], future["mean_temperature_c"]),
              "annual_precipitation_delta_mm": rain_delta,
              "annual_precipitation_delta_percent": 100 * rain_delta / rain_a if rain_delta is not None and rain_a else None}
    months = [{"month": a["month"],
               "baseline_temperature_c": a["mean_temperature_c"], "future_temperature_c": b["mean_temperature_c"],
               "temperature_delta_c": delta(a["mean_temperature_c"], b["mean_temperature_c"]),
               "baseline_precipitation_mm": a["mean_precipitation_mm"], "future_precipitation_mm": b["mean_precipitation_mm"],
               "precipitation_delta_mm": delta(a["mean_precipitation_mm"], b["mean_precipitation_mm"])}
              for a, b in zip(baseline["months"], future["months"])]
    return annual, months


def run(workspace, config_path, online=False):
    workspace = Path(workspace).resolve()
    config_path = Path(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    results, annual_rows, monthly_rows, features, provenance = [], [], [], [], []
    for site in config["sites"]:
        summaries = {}
        coordinates = None
        for label in ("baseline", "future"):
            first, last = config[label]
            records = []
            for start in range(first, last + 1, 5):
                end = min(start + 4, last)
                rows, receipt, transfer = climate.get(workspace, site, date(start, 1, 1), date(end, 12, 31),
                                                       "projection", config["scenario"], online)
                records.extend(rows)
                provenance.append({"period": label, "transfer": transfer, **receipt})
                request = receipt["request"]
                coordinates = [request["longitude"], request["latitude"]]
            summaries[label] = period_statistics(records, first, last)
            annual_rows.extend({"sitecode": site, "period": label, **r} for r in summaries[label]["annual"])
        annual_delta, months = compare(summaries["baseline"], summaries["future"])
        monthly_rows.extend({"sitecode": site, **r} for r in months)
        result = {"sitecode": site, **summaries, "annual_change": annual_delta, "monthly_change": months,
                  "complete_monthly_temperature_comparisons": sum(r["temperature_delta_c"] is not None for r in months),
                  "complete_monthly_precipitation_comparisons": sum(r["precipitation_delta_mm"] is not None for r in months)}
        results.append(result)
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": coordinates},
                         "properties": {"sitecode": site, "scenario": config["scenario"], "model": "ensemble",
                                        "baseline": config["baseline"], "future": config["future"],
                                        **annual_delta, "monthly_change": months,
                                        "wheat_suitability": None, "crop_decision_ready": False}})
    output = workspace / "outputs" / ("regional_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    report = {"method": "same_model_scenario_period_difference_v1", "config": config,
              "config_sha256": digest(config_path), "model": "ensemble",
              "reference_is_observation": False, "crop_decision_ready": False,
              "sites": results, "provenance": provenance,
              "limitations": ["The reference period is also SSP model output; it is not observation or a historical normal.",
                              "An exploratory 5–30-year comparison; internal climate variability matters for short periods.",
                              "Threshold-exceedance counts are not computed from ensemble-mean days.",
                              "If days are missing, the related monthly/annual summary and difference stay empty; missing years are not dropped.",
                              "Point outputs are coordinates of study sites; they are not parcel or farm boundaries.",
                              "A geographic model validated with crop observations and a dynamic soil response are not yet available."]}
    write_json(output / "regional.json", report)
    write_csv(output / "annual.csv", annual_rows)
    write_csv(output / "monthly_changes.csv", monthly_rows)
    write_json(output / "regional_change.geojson", {"type": "FeatureCollection", "features": features})
    text = ["# FieldShift regional climate change", "",
            f"Reference: {config['baseline']}; future: {config['future']}; SSP: {config['scenario']}; model: ensemble.", "",
            "Both periods come from the same projection source. The reference is not an observation. No crop suitability score or migration route is computed here.", "",
            "Full-day mean temperature / total precipitation is computed for each year; years are weighted equally. Difference = future − reference. Percent precipitation difference = 100 × difference / reference; empty for a zero reference.", ""]
    for result in results:
        text.extend([f"## {result['sitecode']}", "", f"Annual differences: {result['annual_change']}", "",
                     f"Complete monthly temperature comparisons: {result['complete_monthly_temperature_comparisons']}/12; precipitation: {result['complete_monthly_precipitation_comparisons']}/12.", "",
                     "| Month | Temperature difference (°C) | Monthly precipitation difference (mm) |", "|---|---:|---:|"])
        for row in result["monthly_change"]:
            display = lambda value: "missing" if value is None else f"{value:.3f}"
            text.append(f"| {row['month']} | {display(row['temperature_delta_c'])} | {display(row['precipitation_delta_mm'])} |")
        text.append("")
    text.extend(["## Limits of interpretation", "", *["- " + s for s in report["limitations"]], "",
                 "NASA source and method: https://power.larc.nasa.gov/docs/services/api/projection/",
                 "https://power.larc.nasa.gov/docs/methodology/data/sources_future/", ""])
    (output / "REGIONAL_REPORT.md").write_text("\n".join(text), encoding="utf-8")
    return output, report
