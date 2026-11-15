"""Local raw -> profile -> normalized tables -> observed P budgets -> report."""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import __version__
from .catalog import SOURCES, selection, source_directory
from .download import validate_cache
from . import analysis, napeshm, pflux
from .storage import save_database
from .tables import digest, is_missing, profile, read_csv, read_zip_csv, write_csv, write_json


def md(value):
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value).replace("|", "\\|").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;")


def run(workspace, dataset="all", with_analysis=False, pilot="all", pilot_config=None):
    workspace = Path(workspace).resolve()
    keys = selection(dataset)
    # Check the complete input set first, before creating a partial result directory.
    provenance = [validate_cache(workspace, key) for key in keys]
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    output = workspace / "outputs" / run_id
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"run_id": run_id, "created_at_utc": now.isoformat(), "software_version": __version__,
                "data_mode": "real_public_source", "status": "running", "datasets": provenance,
                "missing_tokens": ["blank", "NA", "N/A", "NaN", "NULL"],
                "transformations": ["UTF-8 CSV output", "outer whitespace stripped", "missing tokens -> null",
                                    "identifiers preserved as text", "no imputation", "no stock conversion"]}
    if with_analysis:
        pilot_config = Path(pilot_config) if pilot_config is not None else Path(__file__).resolve().parent.parent / "config/pilots.json"
    write_json(output / "manifest.json", manifest)
    database = {}
    profiles = []
    metrics = {}
    analysis_data = None
    try:
        if with_analysis:
            if "napeshm" not in keys:
                raise ValueError("The pilot analysis needs NAPESHM data.")
            manifest["pilot_analysis"] = {"pilot": pilot, "config_name": pilot_config.name, "config_sha256": digest(pilot_config)}
        for key in keys:
            root = source_directory(workspace, key)
            if key == "pflux":
                tables = {Path(spec["name"]).stem: read_csv((root / spec["name"]).read_bytes(), spec["name"])
                          for spec in SOURCES[key]["files"]}
            else:
                tables = read_zip_csv(root / SOURCES[key]["files"][0]["name"])
            for name, table in tables.items():
                result = profile(table)
                result.update(dataset=key, table=name)
                profiles.append(result)
                cleaned = [{col: None if is_missing(value) else value for col, value in row.items()} for row in table.rows]
                write_csv(output / "processed" / key / f"{name}.csv", cleaned, table.headers)
                database[f"{key}_{name}"] = (table.headers, cleaned)
            if key == "pflux":
                rows, comparisons, headers = pflux.prepare(tables["PBudgetData"], tables["DataSourcesAndReferences"])
                datasets = {"budgets": rows, "system_comparison": comparisons,
                            "wheat_budgets": [r for r in rows if r["system_contains_wheat_text"]],
                            "wheat_system_comparison": [r for r in comparisons if r["system_contains_wheat_text"]]}
                metrics[key] = {
                    "source_rows": len(rows), "systems": len({r["system_id"] for r in rows}),
                    "rotation_position_rows": sum(r["record_type"] == "rotation_position" for r in rows),
                    "system_summary_rows": len(comparisons),
                    "wheat_systems": len({r["system_id"] for r in rows if r["contains_wheat_text"]}),
                    "wheat_systems_named_in_summary": sum(r["wheat_evidence"] == "system_name" for r in comparisons),
                    "wheat_systems_from_rotation_only": sum(r["wheat_evidence"] == "rotation_crop_only" for r in comparisons),
                    "unmatched_reference_rows": sum(not r["references_matched"] for r in rows),
                    "unmatched_rotation_reference_rows": sum(not r["references_matched"] and r["record_type"] == "rotation_position" for r in rows),
                    "reference_footnotes": len(pflux.reference_index(tables["DataSourcesAndReferences"])[1]),
                    "nonnumeric_flux_rows": sum(bool(r["nonnumeric_flux_columns"]) for r in rows),
                    "tolerance_kg_p_ha_year": pflux.ROUNDING_TOLERANCE,
                    "agronomic_checks": dict(Counter(r["agronomic_check"] for r in comparisons)),
                    "overall_checks": dict(Counter(r["overall_check"] for r in comparisons)),
                    "notice": "Rotation order is not a calendar year. The budget is not a plant-available P stock; hidrologic_p_form is kept.",
                }
                for name, data in datasets.items():
                    cols = list(data[0]) if data else headers
                    write_csv(output / "processed" / key / f"{name}.csv", data, cols)
                    database[f"{key}_{name}"] = (cols, data)
            else:
                datasets, metrics[key] = napeshm.prepare(tables)
                for name, data in datasets.items():
                    if not data:
                        raise ValueError(f"Expected NAPESHM output table is empty: {name}")
                    cols = list(data[0])
                    write_csv(output / "processed" / key / f"{name}.csv", data, cols)
                    database[f"{key}_{name}"] = (cols, data)
                if with_analysis:
                    analysis_data, metrics["pilot_analysis"] = analysis.prepare(tables, pilot_config, pilot)
                    for name, data in analysis_data.items():
                        cols = list(data[0])
                        write_csv(output / "processed" / "analysis" / f"{name}.csv", data, cols)
                        database[f"analysis_{name}"] = (cols, data)
        write_json(output / "profiles.json", profiles)
        profile_rows = [{"dataset": p["dataset"], "table": p["table"], "row_count": p["row_count"],
                         **{k: v for k, v in col.items() if k != "examples"},
                         "examples": "; ".join(col["examples"])} for p in profiles for col in p["columns"]]
        profile_headers = ["dataset", "table", "row_count", "name", "missing", "nonmissing", "distinct",
                           "numeric_count", "nonnumeric_count", "min", "max", "mean", "examples"]
        write_csv(output / "profiles.csv", profile_rows, profile_headers)
        write_json(output / "metrics.json", metrics)
        manifest["status"] = "completed"
        manifest["result_tables"] = {name: len(rows) for name, (_, rows) in database.items()}
        save_database(output / "fieldshift_data.sqlite3", database, manifest)
        write_report(output, metrics, profiles, database)
        if analysis_data is not None:
            analysis.write_report(output / "PILOT_REPORT.md", analysis_data, metrics["pilot_analysis"])
        write_json(output / "manifest.json", manifest)
    except Exception as error:
        manifest.update(status="failed", error=str(error))
        write_json(output / "manifest.json", manifest)
        raise
    return output, metrics


def write_report(output, metrics, profiles, database):
    lines = ["# FieldShift real-data report", "", "Data sources: P-FLUX and/or NAPESHM, pinned version 1.", "",
             "This report inspects the real source tables and recomputes the existing phosphorus budgets. It makes no new rotation recommendation and no forecast of future soil stocks.", "",
             "## Files", "", "- `profiles.csv` / `profiles.json`: columns, missing values and numeric summaries.",
             "- `processed/`: cleaned and derived CSV tables.",
             "- `fieldshift_data.sqlite3`: local database of the same tables.",
             "- `manifest.json`: source, version, file integrity and processing log.", "",
             "## Tables", "", "| Source | Table | Rows | Columns |", "|---|---|---:|---:|"]
    for p in profiles:
        lines.append(f"| {p['dataset']} | {p['table']} | {p['row_count']} | {p['column_count']} |")
    if "pflux" in metrics:
        m = metrics["pflux"]
        lines.extend(["", "## Phosphorus computation", "",
                      "Agronomic budget = application + atmospheric deposition + irrigation − removal with harvest.", "",
                      "Overall field budget = agronomic budget − recorded hydrological P export.", "",
                      "Unit: kg P/ha/yr. The P form of the hydrological measurement is kept; different forms are not treated as equivalent total P losses.", "",
                      f"{m['source_rows']} records, {m['systems']} systems; {m['rotation_position_rows']} rotation positions and {m['system_summary_rows']} system summaries.", "",
                      f"{m['wheat_systems']} systems contain the word wheat; this text filter is not a crop ontology.", "",
                      f"Of these, {m['wheat_systems_named_in_summary']} are named in the summary and {m['wheat_systems_from_rotation_only']} only in sub-crop records. `wheat_system_comparison.csv` lists all candidate systems.", "",
                      f"Check against the published system budget (±{pflux.ROUNDING_TOLERANCE} kg P/ha/yr rounding tolerance):", "",
                      f"- Agronomic: {m['agronomic_checks']}", f"- Overall: {m['overall_checks']}", "",
                      "`difference` rows were not corrected automatically; they are kept with their differences in `system_comparison.csv`. Missing components are not counted as zero.", "",
                      "First five system summaries:", "",
                      "| System | Rotation | Computed agronomic | Published | Check |", "|---|---|---:|---:|---|"])
        for row in database["pflux_system_comparison"][1][:5]:
            lines.append("| " + " | ".join(md(row[k]) for k in ("system_id", "system_name", "agronomic_calculated", "agronomic_published", "agronomic_check")) + " |")
    if "napeshm" in metrics:
        m = metrics["napeshm"]
        lines.extend(["", "## Soil observations", "",
                      f"{m['sites']} sites, {m['treatments']} treatments, {m['soil_plots']} plots.", "",
                      f"Site flag for wheat: {m['wheat_flagged_sites']} sites. Observations with wheat in the crop phase: {m['wheat_phase_plots']}.", "",
                      f"Candidate sites with real soil observations: {m['wheat_sites_with_soil']}. Candidates missing from the soil table: {m['wheat_sites_without_soil']}. Details: `wheat_site_coverage.csv`.", "",
                      "`site_wheat_flag` means wheat occurs in some plot of a site; it does not mean all observations are wheat.", "",
                      "Total nitrogen (%), H3A nitrate and potentially mineralizable nitrogen are separate indicators. Olsen and Mehlich-3 phosphorus were not merged. ppm/mg kg values were not converted to kg/ha stocks.", "",
                      "`treatment_summary.csv` summarizes the plots within the same site/treatment/indicator. It is not to be read as change over time or as a causal treatment effect.", "",
                      f"The management table has {m['reserved_management_rows']} reserved index rows and {m['management_invalid_links']} unmatched links. Management events were kept separate; soil rows were not duplicated per event."])
    lines.extend(["", "## Next evaluation", "",
                  "First review missing rates, budget differences and measurement methods. Then select comparable treatments within the same experimental site. Sites from different sources were not merged as if they were one experiment.", "",
                  "## Source citations", "",
                  "Williams et al. (2021). LTAR Phosphorus Budget Summary. https://doi.org/10.15482/USDA.ADC/1523365", "",
                  "Soil Health Institute (2024). North American Project to Evaluate Soil Health Measurements. https://doi.org/10.15482/USDA.ADC/25632270", ""])
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
