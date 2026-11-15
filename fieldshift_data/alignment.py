"""Join source seasons, management, historical weather and dated soil targets."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

from . import __version__
from . import climate, napeshm
from .catalog import source_directory
from .download import validate_cache
from .seasons import build_seasons, management_features, normalize_amendment, sampling_links, weather_features
from .storage import save_database
from .tables import digest, numeric, read_zip_csv, unique_index, write_csv, write_json


FEATURE_COLUMNS = ["crop", "tillage_category", "cover_crop_category", "residue_category", "expected_days",
                   "mean_temperature_c", "precipitation_mm", "thermal_sum_above_base_c_days", "frost_index_days", "heat_index_days",
                   "documented_explicit_n_kg_ha", "explicit_n_event_count", "unresolved_amendment_count"]
METADATA_COLUMNS = ["euid", "siteid", "sitecode", "treatmentid", "season_id", "sampling_date", "feature_cutoff", "weather_group"]


def build_observation_rows(soils, treatments, links, seasons, events, weather_by_site, config):
    by_id = {r["season_id"]: r for r in seasons}
    linked, unlinked = [], []
    for soil in soils:
        link = links.get(soil["treatmentid"], {"status": "sampling_date_missing", "sampling_date": None, "season_id": None})
        if link["status"] != "linked_treatment_sampling_event":
            unlinked.append({"euid": soil["euid"], "sitecode": soil["sitecode"], "treatmentid": soil["treatmentid"],
                             "reason": link["status"], "sampling_date": link["sampling_date"]})
            continue
        season = by_id[link["season_id"]]
        sample = date.fromisoformat(link["sampling_date"])
        cutoff = sample - timedelta(days=1)  # No sample hour: exclude the whole sampling day.
        start = date.fromisoformat(season["sow_date"])
        if cutoff < start:
            unlinked.append({"euid": soil["euid"], "sitecode": soil["sitecode"], "treatmentid": soil["treatmentid"],
                             "reason": "no_complete_day_before_sampling", "sampling_date": sample.isoformat()})
            continue
        treatment = treatments[soil["treatmentid"]]
        weather = weather_features(weather_by_site[soil["sitecode"]], start, cutoff, config)
        management = management_features(events, season, cutoff)
        group = f"{soil['sitecode']}:{season['sow_date']}:{cutoff.isoformat()}"
        row = {"euid": soil["euid"], "siteid": soil["siteid"], "sitecode": soil["sitecode"], "treatmentid": soil["treatmentid"],
               "season_id": season["season_id"], "crop": season["crop"], "sampling_date": sample.isoformat(),
               "sampling_date_scope": "treatment_sampling_event_not_plot_timestamp", "weather_group": group,
               "sampling_position": "during_observed_season", "feature_cutoff": cutoff.isoformat(),
               "tillage_category": treatment["eu_tillage"], "cover_crop_category": treatment["eu_cover_crops"],
               "residue_category": treatment["eu_residue"], **weather, **management,
               **{f"target_{indicator}": numeric(soil[indicator]) for indicator in napeshm.INDICATORS}}
        linked.append(row)
    return linked, unlinked


def run(workspace, pilot="all", online=False):
    workspace = Path(workspace).resolve()
    root = Path(__file__).resolve().parent.parent
    config_path, pilot_path = root / "config/season_alignment.json", root / "config/pilots.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    pilots = json.loads(pilot_path.read_text(encoding="utf-8"))
    chosen = list(pilots) if pilot == "all" else [pilot]
    if any(key not in pilots for key in chosen):
        raise ValueError("Pilot definition not found.")
    provenance = validate_cache(workspace, "napeshm")
    tables = read_zip_csv(source_directory(workspace, "napeshm") / "NAPESHM_public_dataset_06032024.zip")
    napeshm.prepare(tables)  # Validate source identities and soil/treatment/site relationships.
    all_treatments = unique_index(tables["treatments"], "treatmentid")
    tids = {tid for key in chosen for tid in pilots[key]["treatments"]}
    treatments = {tid: all_treatments[tid] for tid in tids}
    expected_sites = {pilots[key]["sitecode"] for key in chosen}
    if any(row["sitecode"] not in expected_sites for row in treatments.values()):
        raise ValueError("Pilot treatment does not match the expected site.")
    events = [{"event_id": f"NAP-M{index}", "source_record": index, **row}
              for index, row in enumerate(tables["mgmtdata"].rows, 2) if row["treatmentid"] in tids]
    soils = [row for row in tables["soildata"].rows if row["treatmentid"] in tids]
    seasons, issues = build_seasons(events, config)
    if not seasons:
        raise ValueError("No matchable season found from the source dates.")
    for season in seasons:
        season["all_ambiguous_boundary_dates"] = ";".join(sorted({s["ambiguous_boundary_date"] for s in seasons
            if s["treatmentid"] == season["treatmentid"] and s["ambiguous_boundary_date"]}))
    links = sampling_links(events, seasons, config)
    now = datetime.now(timezone.utc)
    output = workspace / "outputs" / ("seasons_" + now.strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    manifest = {"software_version": __version__, "status": "running", "created_at_utc": now.isoformat(),
                "source": provenance, "config_sha256": digest(config_path), "pilots_sha256": digest(pilot_path),
                "link_resolution": {"soil": "plot", "management": "treatment", "weather": "site_grid_cell"},
                "weather_requests": [], "target_campaign_year": config["soil_campaign_year"]}
    write_json(output / "manifest.json", manifest)
    try:
        weather_by_site = {}
        for sitecode in sorted(expected_sites):
            site_seasons = [s for s in seasons if s["sitecode"] == sitecode]
            if not site_seasons:
                continue
            start = min(date.fromisoformat(s["sow_date"]) for s in site_seasons)
            end = max(date.fromisoformat(s["harvest_date"]) for s in site_seasons)
            print(f"Season weather: {sitecode} {start} → {end}", flush=True)
            rows, receipt, transfer = climate.get(workspace, sitecode, start, end, "historical", online=online)
            weather_by_site[sitecode] = rows
            manifest["weather_requests"].append({"sitecode": sitecode, "receipt": receipt, "transfer": transfer})
        summaries = []
        for season in seasons:
            start, end = date.fromisoformat(season["sow_date"]), date.fromisoformat(season["harvest_date"])
            summaries.append({**season, **weather_features(weather_by_site[season["sitecode"]], start, end, config),
                              **management_features(events, season, end)})
        observations, unlinked = build_observation_rows(soils, treatments, links, seasons, events, weather_by_site, config)
        amendments = [{"treatmentid": event["treatmentid"], "sitecode": event["sitecode"], "date": event["date"],
                       "description": event["eventdesc"], **normalize_amendment(event)} for event in events if event["category"] == "amendment"]
        dictionary = [dict(r) for r in tables["dbcolumns"].rows if r["dbtablename"] == "soildata" and r["dbcolname"] in napeshm.INDICATORS]
        links_rows = [{"treatmentid": tid, **link} for tid, link in sorted(links.items())]
        groups = sorted({r["weather_group"] for r in observations})
        readiness = {"aligned_soil_plots": len(observations), "unlinked_soil_plots": len(unlinked),
                     "source_seasons": len(seasons), "source_soil_plots": len(soils),
                     "linked_weather_groups": len(groups), "weather_groups": groups,
                     "aligned_rows_with_complete_weather": sum(r["complete_weather"] for r in observations),
                     "unlinked_reasons": dict(Counter(r["reason"] for r in unlinked)),
                     "dynamic_soil_model_ready": False,
                     "reasons": ["Single-campaign soil targets: no before/after soil measurements per plot.",
                                 "Crop yields and nutrient removal amounts are not identified from harvest residue percentages.",
                                 "P/K amendment amounts and N fixation/losses are unresolved.",
                                 "Management dates are treatment-level; exact plot sampling times and experimental blocks are unresolved.",
                                 "Shared site weather must not be treated as independent climate observations per plot."],
                     "feature_timing": "Only complete days strictly before soil sampling; targets are not initial soil features.",
                     "nutrient_scope": "Explicit documented N subtotal only; zero subtotal is not proof of zero total fertilizer input."}
        datasets = {"observed_seasons": summaries, "management_events": events, "amendment_audit": amendments,
                    "sampling_links": links_rows, "features_at_sampling": observations,
                    "unlinked_soil": unlinked, "target_dictionary": dictionary}
        database = {}
        empty_headers = {"features_at_sampling": METADATA_COLUMNS + FEATURE_COLUMNS + [f"target_{i}" for i in napeshm.INDICATORS],
                         "unlinked_soil": ["euid", "sitecode", "treatmentid", "reason", "sampling_date"],
                         "amendment_audit": ["event_id", "treatmentid", "date", "explicit_n_kg_ha", "basis_status"]}
        for name, rows in datasets.items():
            headers = list(rows[0]) if rows else empty_headers.get(name, ["status"])
            write_csv(output / f"{name}.csv", rows, headers)
            database[name] = (headers, rows)
        write_csv(output / "season_issues.csv", issues, ["treatmentid", "event_id", "reason", "detail"])
        write_json(output / "readiness.json", readiness)
        write_json(output / "training_contract.json", {"feature_columns": FEATURE_COLUMNS,
                   "target_columns": [f"target_{i}" for i in napeshm.INDICATORS],
                   "group_column": "weather_group", "use_for_dynamic_model_training": False,
                   "metadata_columns": METADATA_COLUMNS,
                   "note": "Candidate aligned table, not a validated training set. Do not split replicated weather groups randomly across train and test."})
        manifest.update(status="completed", readiness=readiness)
        save_database(output / "aligned_data.sqlite3", database, manifest)
        write_json(output / "manifest.json", manifest)
        report(output, summaries, observations, readiness)
    except Exception as error:
        manifest.update(status="failed", error=str(error))
        write_json(output / "manifest.json", manifest)
        raise
    return output, readiness


def report(output, seasons, observations, readiness):
    lines = ["# FieldShift same-site and season alignment", "",
             f"Source seasons: {len(seasons)}. Soil observations: {readiness['source_soil_plots']}; linked by date: {len(observations)}; not linked: {readiness['unlinked_soil_plots']}.", "",
             "## Calendar derived from the source", "",
             "The rows below show treatments with the same site/crop/calendar once; the CSV has details per treatment.", "",
             "| Site | Crop | Sowing | Harvest | Days |", "|---|---|---|---|---:|"]
    seen = set()
    for row in seasons:
        key = (row["sitecode"], row["crop"], row["sow_date"], row["harvest_date"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"| {row['sitecode']} | {row['crop']} | {row['sow_date']} | {row['harvest_date']} | {row['duration_days']} |")
    lines += ["", "## Timing relative to soil measurement", "",
              "The sampling date comes from the treatment-level soil sampling event in the source management table. It is not a per-plot timestamp. As the time of day is unknown, weather and management features are cut at the end of the previous day.", "",
              "| Site | Sampling | Last day of features | Days since sowing | Documented N (kg N/ha) |", "|---|---|---|---:|---:|"]
    seen = set()
    for row in observations:
        key = (row["sitecode"], row["treatmentid"], row["sampling_date"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"| {row['sitecode']} / {row['treatmentid']} | {row['sampling_date']} | {row['feature_cutoff']} | {row['expected_days']} | {row['documented_explicit_n_kg_ha']:.3f} |")
    lines += ["", f"Reasons for unlinked records: {readiness['unlinked_reasons']}", "",
              f"Shared weather groups among linked observations (not independent): {readiness['linked_weather_groups']}.", "",
              "## Interpretation", "",
              "The full-season weather summary is in observed_seasons.csv. Days after sampling are not included in features_at_sampling.csv. The % residue removed at harvest is not crop yield; the STIR machinery/disturbance index is not a seed or fertilizer amount.", "",
              "N conversion is applied only to records whose unit is clearly elemental N. Product mass, seed or fertilizer label percentages are not converted automatically to N/P/K. Unknown P/K stays empty. Fertilizer events on a same-day harvest/sowing boundary are set aside as ambiguous.", "",
              "Thermal sum above 0 °C, days with minimum below 0 °C and days with maximum above 35 °C are environmental indices. They are not a wheat development model or a damage forecast.", "",
              "## Model readiness", "", "Dynamic soil model training: **not ready**. Before/after soil measurements on the same plot, crop yields and harvest nutrient removals are missing. Repeated weather of the same site does not count as many independent climate samples.", "",
              "This version links the real sowing/harvest/sampling calendar to the correct historical weather. It produces the joined table and the record of gaps needed for the next process calibration.", "",
              "Sources: https://doi.org/10.15482/USDA.ADC/25632270 and https://power.larc.nasa.gov/docs/services/api/temporal/daily/", ""]
    (output / "SEASON_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
