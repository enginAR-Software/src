"""Descriptive within-site pilot comparisons; no causal or predictive claims."""

from collections import defaultdict
import json
from pathlib import Path
import statistics

from .napeshm import INDICATORS
from .tables import is_missing, numeric, unique_index


def descriptive(raw_values):
    values = [value for raw in raw_values if (value := numeric(raw)) is not None]
    missing = sum(is_missing(raw) for raw in raw_values)
    return {
        "n_total": len(raw_values), "n_numeric": len(values), "n_missing": missing,
        "n_unparsed": len(raw_values) - missing - len(values),
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "min": min(values) if values else None, "max": max(values) if values else None,
        "sd_sample": statistics.stdev(values) if len(values) > 1 else None,
    }


def mean_difference(a, b):
    for key in ("siteid", "indicator", "unit", "method"):
        if a[key] != b[key]:
            raise ValueError(f"Comparison mismatch: {key}.")
    difference = b["mean"] - a["mean"] if a["mean"] is not None and b["mean"] is not None else None
    return {"mean_a": a["mean"], "mean_b": b["mean"], "n_a": a["n_numeric"], "n_b": b["n_numeric"],
            "difference_b_minus_a": difference,
            "difference_unit": "percentage_points" if a["unit"] == "%" else a["unit"],
            "status": "descriptive_only" if difference is not None else "missing_measurement"}


def prepare(tables, config_path, pilot="all"):
    configs = json.loads(Path(config_path).read_text(encoding="utf-8"))
    keys = list(configs) if pilot == "all" else [pilot]
    if not keys or any(key not in configs for key in keys):
        raise ValueError("Pilot configuration not found.")
    sites = unique_index(tables["sites"], "siteid")
    treatments = unique_index(tables["treatments"], "treatmentid")
    dictionary = {(r["dbtablename"], r["dbcolname"]): r for r in tables["dbcolumns"].rows}
    plots, summaries, contrasts, selected_treatments, selected_sites = [], [], [], [], []
    counts = {}
    for key in keys:
        config = configs[key]
        site = sites.get(config["siteid"])
        if site is None or site["sitecode"] != config["sitecode"]:
            raise ValueError(f"Pilot site id does not match: {key}")
        selected_sites.append({"pilot": key, **site})
        selected_ids = config["treatments"]
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("Duplicate treatment id within a pilot.")
        for tid in selected_ids:
            treatment = treatments.get(tid)
            if (treatment is None or treatment["siteid"] != config["siteid"]
                    or treatment["crop_phase"] != config["expected_phase"]):
                raise ValueError(f"Pilot treatment or crop phase does not match: {tid}")
            selected_treatments.append({"pilot": key, **treatment})
        observations = [r for r in tables["soildata"].rows
                        if r["siteid"] == config["siteid"] and r["treatmentid"] in selected_ids]
        if not observations:
            raise ValueError(f"No soil observations for pilot: {key}")
        grouped = defaultdict(list)
        for row in observations:
            treatment = treatments[row["treatmentid"]]
            for indicator in INDICATORS:
                meta = dictionary[("soildata", indicator)]
                raw = row[indicator]
                value = numeric(raw)
                plots.append({"pilot": key, "siteid": row["siteid"], "sitecode": row["sitecode"],
                              "treatmentid": row["treatmentid"], "euid": row["euid"], "eucode": row["eucode"],
                              "treatment_description": treatment["eu_treat_desc"], "crop_phase": treatment["crop_phase"],
                              "indicator": indicator, "value": value, "raw_value": raw,
                              "unit": meta["unit"], "method": meta["description"],
                              "value_status": "missing" if is_missing(raw) else "numeric" if value is not None else "unparsed"})
                grouped[(row["treatmentid"], indicator)].append(raw)
        stats = {}
        for tid in selected_ids:
            for indicator in INDICATORS:
                meta = dictionary[("soildata", indicator)]
                summary = {"pilot": key, "siteid": config["siteid"], "treatmentid": tid,
                           "treatment_description": treatments[tid]["eu_treat_desc"], "indicator": indicator,
                           "unit": meta["unit"], "method": meta["description"],
                           **descriptive(grouped[(tid, indicator)])}
                summaries.append(summary)
                stats[(tid, indicator)] = summary
        for pair in config["contrasts"]:
            if pair["a"] not in selected_ids or pair["b"] not in selected_ids or pair["a"] == pair["b"]:
                raise ValueError("Comparison treatments must be two different treatments within the pilot.")
            for indicator in INDICATORS:
                a, b = stats[(pair["a"], indicator)], stats[(pair["b"], indicator)]
                contrasts.append({"pilot": key, "siteid": config["siteid"], "label": pair["label"],
                                  "treatment_a": pair["a"], "treatment_b": pair["b"], "indicator": indicator,
                                  "unit": a["unit"], "method": a["method"], **mean_difference(a, b)})
        counts[key] = {"sitecode": site["sitecode"], "label": config["label"],
                       "plot_count": len(observations), "treatment_count": len(selected_ids),
                       "crop_phase": config["expected_phase"], "contrast_definitions": len(config["contrasts"])}
    metrics = {"pilots": counts, "selected_plots": sum(p["plot_count"] for p in counts.values()),
               "indicator_rows": len(plots), "summary_rows": len(summaries), "contrast_rows": len(contrasts),
               "contrasts_with_values": sum(r["status"] == "descriptive_only" for r in contrasts),
               "notice": "Mean differences are descriptive. No claim of causality, paired measurement, significance or future forecast is made."}
    return {"pilot_sites": selected_sites, "pilot_treatments": selected_treatments,
            "pilot_plots": plots, "pilot_summary": summaries, "pilot_contrasts": contrasts}, metrics


def write_report(path, data, metrics):
    def fmt(value):
        return "—" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value).replace("|", "\\|")

    lines = ["# FieldShift pilot analysis report", "",
             "Descriptive statistics computed from individual plots. Source: NAPESHM, version 1.", "",
             "Mean difference is B − A. Differences in % units are percentage points, not relative percent change. pH differences are in pH units.", "",
             "Sample standard deviation uses n−1. With one or zero measurements the standard deviation is left empty. Missing values are not counted as zero.", ""]
    for key, info in metrics["pilots"].items():
        lines.extend([f"## {info['label']}", "",
                      f"{info['plot_count']} plots, {info['treatment_count']} treatments. Measurement phase: {info['crop_phase']}.", "",
                      "| Treatment | Description in the source |", "|---|---|"])
        for row in data["pilot_treatments"]:
            if row["pilot"] == key:
                lines.append(f"| {row['treatmentid']} | {fmt(row['eu_treat_desc'])} |")
        lines.extend(["", "Organic carbon summary (source unit: %):", "",
                      "| Treatment | n | Mean | Median | Sample SD | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"])
        for row in data["pilot_summary"]:
            if row["pilot"] == key and row["indicator"] == "b_soc":
                lines.append("| " + " | ".join(fmt(row[k]) for k in ("treatmentid", "n_numeric", "mean", "median", "sd_sample", "min", "max")) + " |")
        lines.extend(["", "Organic carbon mean differences (percentage points, B − A):", "",
                      "| Comparison | A | B | Difference |", "|---|---|---|---:|"])
        for row in data["pilot_contrasts"]:
            if row["pilot"] == key and row["indicator"] == "b_soc":
                lines.append("| " + " | ".join(fmt(row[k]) for k in ("label", "treatment_a", "treatment_b", "difference_b_minus_a")) + " |")
        lines.append("")
    lines.extend(["## Limits of interpretation", "",
                  "In Oregon the crop order is the same and tillage differs. In Kansas the measurement phase is sorghum; it is not to be read as a wheat-phase measurement. Nitrogen levels are labels in the treatment description; the actual yearly fertilizer schedule is not derived from them.", "",
                  "Observations were not paired before experimental blocks and statistical independence were verified; no p-values or significance tests were produced. A mean difference is not a future rate of change or a causal effect. No best-rotation ranking was made.", "",
                  "Counts and distributions of all 9 indicators are in `processed/analysis/pilot_summary.csv`, individual values in `pilot_plots.csv`, comparisons in `pilot_contrasts.csv`.", "",
                  "Soil Health Institute (2024). https://doi.org/10.15482/USDA.ADC/25632270 — CC BY 4.0. Raw files are kept; the statistics shown are derived.", ""])
    Path(path).write_text("\n".join(lines), encoding="utf-8")
