"""Source-dated crop seasons and strictly time-bounded feature calculations."""

from collections import defaultdict
from datetime import date, timedelta
import statistics

from .tables import numeric


LB_PER_ACRE_TO_KG_PER_HA = 0.45359237 * 10000 / 4046.8564224


def crop_name(description, config):
    text = description.casefold()
    matches = [crop for crop, aliases in config["crop_aliases"].items() if any(alias.casefold() in text for alias in aliases)]
    return matches[0] if len(matches) == 1 else None


def normalize_amendment(event):
    unit = " ".join(event["unit"].casefold().split())
    quantity = numeric(event["quantity"])
    factor = LB_PER_ACRE_TO_KG_PER_HA if unit in ("lbs acre-1 n", "lb acre-1 n") else 1 if unit in ("kg n/ha", "kg ha-1 n", "kg n ha-1") else None
    value = quantity * factor if quantity is not None and quantity >= 0 and factor is not None else None
    return {"event_id": event.get("event_id", ""), "source_quantity": event["quantity"], "source_unit": event["unit"],
            "explicit_n_kg_ha": value, "basis_status": "explicit_elemental_n" if value is not None else "unresolved_basis_or_quantity",
            "p_kg_ha": None, "k_kg_ha": None}


def build_seasons(events, config):
    grouped = defaultdict(list)
    issues = []
    for index, event in enumerate(events, 1):
        day = date.fromisoformat(event["date"])
        record = {**event, "event_id": event.get("event_id", f"E{index}"), "day": day}
        grouped[event["treatmentid"]].append(record)
    seasons = []
    for tid, records in grouped.items():
        records.sort(key=lambda r: (r["day"], r["event_id"]))
        plants, harvests = {}, []
        for event in records:
            if event["category"] not in ("plant cash crop", "harvest"):
                continue
            if event["unit"].casefold() == "stir":
                continue
            crop = crop_name(event["eventdesc"], config)
            if crop is None:
                issues.append({"treatmentid": tid, "event_id": event["event_id"], "reason": "crop_alias_unresolved", "detail": event["eventdesc"]})
                continue
            item = {**event, "crop": crop}
            if event["category"] == "plant cash crop":
                plants.setdefault((event["day"], crop), item)
            else:
                harvests.append(item)
        ordered = sorted(plants.values(), key=lambda r: (r["day"], r["crop"]))
        for index, plant in enumerate(ordered):
            candidates = [h for h in harvests if h["crop"] == plant["crop"] and h["day"] >= plant["day"]]
            if not candidates:
                issues.append({"treatmentid": tid, "event_id": plant["event_id"], "reason": "matching_harvest_missing", "detail": plant["eventdesc"]})
                continue
            harvest = min(candidates, key=lambda r: r["day"])
            if index + 1 < len(ordered) and ordered[index + 1]["day"] < harvest["day"]:
                issues.append({"treatmentid": tid, "event_id": plant["event_id"], "reason": "overlapping_cash_seasons", "detail": plant["eventdesc"]})
                continue
            previous = [h["day"] for h in harvests if h["day"] <= plant["day"]]
            markers = [r["day"] for r in records if r["category"] == "reserved index row" and r["eventdesc"].casefold() == "start"]
            first = min(markers) if markers else min(r["day"] for r in records)
            management_start = min(max(previous) + timedelta(days=1), plant["day"]) if previous else first
            boundary = max(previous).isoformat() if previous and max(previous) == plant["day"] else ""
            seasons.append({"season_id": f"{plant['sitecode']}:{tid}:{plant['day'].isoformat()}:{plant['crop']}",
                            "sitecode": plant["sitecode"], "treatmentid": tid, "crop": plant["crop"],
                            "sow_date": plant["day"].isoformat(), "harvest_date": harvest["day"].isoformat(),
                            "management_window_start": management_start.isoformat(), "ambiguous_boundary_date": boundary,
                            "duration_days": (harvest["day"] - plant["day"]).days + 1,
                            "plant_event_id": plant["event_id"], "harvest_event_id": harvest["event_id"],
                            "harvest_quantity_raw": harvest["quantity"], "harvest_unit_raw": harvest["unit"],
                            "yield_kg_ha": None, "yield_status": "yield_not_extracted_from_residue_or_machine_records"})
    return seasons, issues


def sampling_links(events, seasons, config):
    output = {}
    for tid in sorted({event["treatmentid"] for event in events}):
        sampling = sorted({event["date"] for event in events if event["treatmentid"] == tid and event["category"] == "soil sampling"
                           and date.fromisoformat(event["date"]).year == config["soil_campaign_year"]})
        if not sampling:
            output[tid] = {"status": "sampling_date_missing", "sampling_date": None, "season_id": None}
        elif len(sampling) != 1:
            output[tid] = {"status": "sampling_date_ambiguous", "sampling_date": None, "season_id": None}
        else:
            candidates = [s for s in seasons if s["treatmentid"] == tid and s["sow_date"] <= sampling[0] <= s["harvest_date"]]
            output[tid] = {"status": "linked_treatment_sampling_event" if len(candidates) == 1 else "sampling_outside_or_ambiguous_season",
                           "sampling_date": sampling[0], "season_id": candidates[0]["season_id"] if len(candidates) == 1 else None}
    return output


def weather_features(rows, start, end, config):
    if start > end:
        raise ValueError("Weather feature start cannot be after its end.")
    selected = {}
    for row in rows:
        day = date.fromisoformat(row["date"])
        if start <= day <= end:
            if day in selected:
                raise ValueError("Two weather records for the same day.")
            selected[day] = row
    expected = (end - start).days + 1
    values = {p: [numeric(row.get(p)) for row in selected.values()] for p in ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR")}
    valid = {p: [v for v in numbers if v is not None] for p, numbers in values.items()}
    complete = {p: len(numbers) == expected for p, numbers in valid.items()}
    return {"weather_start": start.isoformat(), "weather_end": end.isoformat(), "expected_days": expected,
            "temperature_days": len(valid["T2M"]), "precipitation_days": len(valid["PRECTOTCORR"]),
            "complete_weather": all(complete.values()),
            "mean_temperature_c": statistics.fmean(valid["T2M"]) if complete["T2M"] else None,
            "precipitation_mm": sum(valid["PRECTOTCORR"]) if complete["PRECTOTCORR"] else None,
            "thermal_sum_above_base_c_days": sum(max(0, x - config["weather_index_base_c"]) for x in valid["T2M"]) if complete["T2M"] else None,
            "frost_index_days": sum(x < 0 for x in valid["T2M_MIN"]) if complete["T2M_MIN"] else None,
            "heat_index_days": sum(x > config["weather_index_heat_c"] for x in valid["T2M_MAX"]) if complete["T2M_MAX"] else None}


def management_features(events, season, cutoff):
    start = date.fromisoformat(season["management_window_start"])
    boundary_dates = {date.fromisoformat(s) for s in season.get("all_ambiguous_boundary_dates", "").split(";") if s}
    included = [e for e in events if e["treatmentid"] == season["treatmentid"] and e["category"] != "reserved index row"
                and start <= date.fromisoformat(e["date"]) <= cutoff]
    amendments = [e for e in included if e["category"] == "amendment"]
    unresolved = [e for e in amendments if date.fromisoformat(e["date"]) in boundary_dates or normalize_amendment(e)["explicit_n_kg_ha"] is None]
    known = [normalize_amendment(e)["explicit_n_kg_ha"] for e in amendments if e not in unresolved]
    return {"management_start": start.isoformat(), "management_cutoff": cutoff.isoformat(),
            "documented_explicit_n_kg_ha": sum(known), "explicit_n_event_count": len(known),
            "unresolved_amendment_count": len(unresolved),
            "amendment_event_count": len(amendments),
            "documented_p_input_kg_ha": None, "documented_k_input_kg_ha": None,
            "event_count": len(included), "coverage_scope": "documented_events_only",
            "event_ids": ";".join(e.get("event_id", "") for e in included)}
