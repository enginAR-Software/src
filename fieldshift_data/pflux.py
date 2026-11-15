"""Observed P budgets. Rotation position is not a calendar year."""

import json
import re
from .tables import numeric, require


ANNUAL = {
    "application": "Annual average P application rate (kg/ha)",
    "deposition": "Average annual atmospheric P deposition (kg/ha)",
    "irrigation": "Annual average P in irrigation (kg/ha)",
    "removal": "Annual average P removed by crop (kg/ha)",
    "surface": "Annual average surface P loads (kg/ha)",
    "subsurface": "Annual average subsurface P loads (kg/ha)",
}
SYSTEM = {
    "application": "System average P application rate (kg/ha)",
    "deposition": "System average atmospheric P deposition (kg/ha)",
    "irrigation": "System average P in irrigation (kg/ha)",
    "removal": "System average crop P removal (kg/ha)",
    "hydrology": "System average hydrologic P loads (kg/ha)",
}
PUBLISHED_AGRONOMIC = "System average agronomic P budgets (kg/ha)"
PUBLISHED_OVERALL = "System average overall field P budgets (kg/ha)"
IDENTITY = ["Location", "Cropping system ID", "Rotation year"]
ROUNDING_TOLERANCE = 0.03


def budget(flows):
    required = ("application", "deposition", "irrigation", "removal")
    absent = [key for key in required if flows.get(key) is None]
    agronomic = None if absent else sum(flows[k] for k in required[:3]) - flows["removal"]
    hydro = flows.get("hydrology")
    if "hydrology" not in flows:
        if flows.get("surface") is not None and flows.get("subsurface") is not None:
            hydro = flows["surface"] + flows["subsurface"]
    overall = agronomic - hydro if agronomic is not None and hydro is not None else None
    return {"agronomic": agronomic, "overall": overall,
            "missing_fluxes": absent + (["hydrology"] if hydro is None else [])}


def identity(row):
    return tuple(row[k] for k in IDENTITY)


def reference_index(references):
    require(references, IDENTITY)
    result = {}
    notes = []
    for row in references.rows:
        key = identity(row)
        if not any(key) and row.get("Notes") and not any(v for k, v in row.items() if k != "Notes"):
            notes.append(row)
            continue
        if not all(key) or key in result:
            raise ValueError(f"Empty/duplicate key in the P-FLUX source table: {key}")
        result[key] = row
    return result, notes


def prepare(data, references):
    require(data, IDENTITY + ["Crop names", "Dominant cropping system name", "Analyzed hydrologic P form",
                             PUBLISHED_AGRONOMIC, PUBLISHED_OVERALL] + list(ANNUAL.values()) + list(SYSTEM.values()))
    ref_map, _ = reference_index(references)
    rows = []
    comparisons = []
    seen = set()
    for line, row in enumerate(data.rows, 2):
        key = identity(row)
        if key in seen:
            raise ValueError(f"Duplicate key in the P-FLUX data table: {key}")
        seen.add(key)
        label = row["Rotation year"]
        if label.startswith("System "):
            kind, rotation = "system_summary", None
        elif match := re.fullmatch(r"(\d+)(?:\s*\(no rotation\))?", label):
            kind, rotation = "rotation_position", int(match.group(1))
        else:
            raise ValueError(f"Bilinmeyen rotasyon etiketi: {label}")
        mapping = SYSTEM if kind == "system_summary" else ANNUAL
        flows = {name: numeric(row[column]) for name, column in mapping.items()}
        invalid = [column for column in mapping.values()
                   if row[column].casefold() not in {"", "na", "n/a", "nan", "null"}
                   and numeric(row[column]) is None]
        if any(v is not None and v < 0 for v in flows.values()):
            raise ValueError(f"{key}: negative P input/output component.")
        calculated = budget(flows)
        record = {
            "source_row": line, "location": row["Location"], "system_id": row["Cropping system ID"],
            "system_name": row["Dominant cropping system name"], "record_type": kind,
            "rotation_label": label, "rotation_position": rotation, "crop": row["Crop names"],
            "contains_wheat_text": bool(re.search(r"wheat", row["Dominant cropping system name"] + " " + row["Crop names"], re.I)),
            "unit": "kg P/ha/year (rotation-position or system average)",
            **{f"{k}_p": v for k, v in flows.items()},
            "agronomic_p_budget": calculated["agronomic"], "overall_p_budget": calculated["overall"],
            "hydrologic_p_form": row["Analyzed hydrologic P form"],
            "missing_fluxes": ";".join(calculated["missing_fluxes"]),
            "nonnumeric_flux_columns": ";".join(invalid),
            "references_matched": key in ref_map,
        }
        # Normalize variable shapes before CSV export.
        for flux in ("application", "deposition", "irrigation", "removal", "surface", "subsurface", "hydrology"):
            record.setdefault(f"{flux}_p", None)
        context = [ref for ref_key, ref in ref_map.items() if ref_key[:2] == key[:2]]
        record["provenance_match"] = "exact" if key in ref_map else "system_context" if context else "missing"
        record["provenance_json"] = json.dumps(ref_map[key] if key in ref_map else context, ensure_ascii=False, sort_keys=True)
        rows.append(record)
        if kind == "system_summary":
            comparison = {"location": record["location"], "system_id": record["system_id"],
                          "system_name": record["system_name"], "contains_wheat_text": record["contains_wheat_text"],
                          "hydrologic_p_form": record["hydrologic_p_form"]}
            for metric, source_column in (("agronomic", PUBLISHED_AGRONOMIC), ("overall", PUBLISHED_OVERALL)):
                published = numeric(row[source_column])
                value = calculated[metric]
                error = value - published if value is not None and published is not None else None
                comparison.update({f"{metric}_calculated": value, f"{metric}_published": published,
                                   f"{metric}_difference": error,
                                   f"{metric}_check": "missing" if error is None else "within_rounding" if abs(error) <= ROUNDING_TOLERANCE + 1e-12 else "difference"})
            comparisons.append(comparison)
    wheat_ids = {row["system_id"] for row in rows if row["contains_wheat_text"]}
    name_ids = {row["system_id"] for row in comparisons if row["contains_wheat_text"]}
    for record in rows + comparisons:
        sid = record["system_id"]
        record["system_contains_wheat_text"] = sid in wheat_ids
        record["wheat_evidence"] = "system_name" if sid in name_ids else "rotation_crop_only" if sid in wheat_ids else "none"
    # Explicit shared order; summary-only and position-only columns remain blank.
    headers = list(rows[0]) if rows else []
    return rows, comparisons, headers
