"""Component C: the economically most efficient crop rotation per parcel.

Objective: total expected profit over the plan years (USD/acre)
    profit(year) = yield × rotation_multiplier(previous→crop) × price − production cost − P replacement cost
P replacement cost = the crop's P removal from P-FLUX (kg/ha → kg/acre) × P fertilizer price.

No yield, price or cost is ever invented. Values come either from config/economics_inputs.csv, filled in by the user
with a source for every value, or from the USDA NASS Quick Stats API.
"""

from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
from statistics import median
import tempfile
import urllib.parse

from .download import atomic_json, request_bytes
from .tables import digest

ACRES_PER_HA = 2.4710538
WHEAT_CROPS = {"Winter Wheat", "Spring Wheat"}
CDL_TO_CROP = {
    "Corn": "Corn", "Soybeans": "Soybeans", "Sorghum": "Sorghum", "Winter Wheat": "Winter Wheat",
    "Spring Wheat": "Spring Wheat", "Durum Wheat": "Spring Wheat", "Peas": "Peas",
    "Fallow/Idle Cropland": "Fallow/Idle Cropland", "Alfalfa": "Alfalfa",
    "Other Hay/Non Alfalfa": "Other Hay/Non Alfalfa", "Triticale": "Triticale", "Canola": "Canola",
    "Dbl Crop WinWht/Soybeans": "Dbl Crop WinWht/Soybeans", "Barley": "Barley", "Oats": "Oats",
}
PFLUX_CROPS = {"Corn": ["Corn"], "Soybeans": ["Soybean"], "Sorghum": ["Sorghum"],
               "Winter Wheat": ["Winter wheat", "Wheat"], "Spring Wheat": ["Spring wheat"],
               "Canola": ["Canola"], "Alfalfa": ["Alfalfa"], "Barley": ["Barley"]}
NASS_SERIES = {
    "Winter Wheat": {"yield": "WHEAT, WINTER - YIELD, MEASURED IN BU / ACRE", "price": "WHEAT - PRICE RECEIVED, MEASURED IN $ / BU", "unit": "BU", "price_factor": 1.0},
    "Spring Wheat": {"yield": "WHEAT, SPRING, (EXCL DURUM) - YIELD, MEASURED IN BU / ACRE", "price": "WHEAT - PRICE RECEIVED, MEASURED IN $ / BU", "unit": "BU", "price_factor": 1.0},
    "Corn": {"yield": "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE", "price": "CORN, GRAIN - PRICE RECEIVED, MEASURED IN $ / BU", "unit": "BU", "price_factor": 1.0},
    "Soybeans": {"yield": "SOYBEANS - YIELD, MEASURED IN BU / ACRE", "price": "SOYBEANS - PRICE RECEIVED, MEASURED IN $ / BU", "unit": "BU", "price_factor": 1.0},
    "Sorghum": {"yield": "SORGHUM, GRAIN - YIELD, MEASURED IN BU / ACRE", "price": "SORGHUM, GRAIN - PRICE RECEIVED, MEASURED IN $ / CWT", "unit": "BU", "price_factor": 0.56},
}
NASS_NOTE = "Sorghum price is published in $/CWT; assuming 1 bu sorghum = 56 lb, $/bu = $/CWT × 0.56."
INPUT_FIELDS = ["region", "crop", "yield_per_acre", "yield_unit", "price_usd_per_unit", "cost_usd_per_acre",
                "yield_source", "price_source", "cost_source", "source_years"]


def number(value):
    if value is None or str(value).strip() == "":
        return None
    result = float(str(value).replace(",", ""))
    if result != result or result < 0:
        raise ValueError(f"Negative or invalid number: {value}")
    return result


def validate_config(config):
    if type(config.get("plan_start_year")) is not int or type(config.get("years")) is not int:
        raise ValueError("plan_start_year and years must be integers.")
    if not 2 <= config["years"] <= 8:
        raise ValueError("The plan must be 2–8 years long (exhaustive search).")
    if type(config.get("max_consecutive_same_crop")) is not int or config["max_consecutive_same_crop"] < 1:
        raise ValueError("max_consecutive_same_crop must be at least 1.")
    if not isinstance(config.get("allowed_crops"), dict):
        raise ValueError("allowed_crops must map region → list of crops.")
    for effect in config.get("rotation_effects", []):
        if not effect.get("source") or not isinstance(effect.get("yield_multiplier"), (int, float)) or effect["yield_multiplier"] <= 0:
            raise ValueError("Each rotation effect needs a positive yield_multiplier and a source.")
    for region, rule in config.get("fallow_requirement", {}).items():
        if type(rule.get("max_years_without_fallow")) is not int or rule["max_years_without_fallow"] < 1 or not rule.get("source"):
            raise ValueError(f"{region}: fallow_requirement needs a positive max_years_without_fallow and a source.")
    for key in ("p_fertilizer_price_usd_per_kg_p", "fallow_cost_usd_per_acre"):
        if config.get(key) is not None:
            number(config[key])
            if not config.get(key.replace("_usd_per_kg_p", "_source").replace("_usd_per_acre", "_source")):
                raise ValueError(f"If {key} is given, its source must be given too.")


def load_inputs(path):
    """region,crop → values. Every value entered must have a source."""
    path = Path(path)
    if not path.is_file():
        return {}
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    result = {}
    for row in rows:
        if set(INPUT_FIELDS) - set(row):
            raise ValueError(f"economics_inputs.csv is missing columns: {sorted(set(INPUT_FIELDS) - set(row))}")
        key = (row["region"].strip(), row["crop"].strip())
        if key in result:
            raise ValueError(f"economics_inputs.csv has a duplicate row: {key}")
        entry = {"yield": number(row["yield_per_acre"]), "unit": row["yield_unit"].strip() or None,
                 "price": number(row["price_usd_per_unit"]), "cost": number(row["cost_usd_per_acre"]),
                 "yield_source": row["yield_source"].strip(), "price_source": row["price_source"].strip(),
                 "cost_source": row["cost_source"].strip(), "source_years": row["source_years"].strip(),
                 "origin": "economics_inputs.csv"}
        for field in ("yield", "price", "cost"):
            if entry[field] is not None and not entry[f"{field}_source"]:
                raise ValueError(f"{key}: a {field} value was entered but its source is empty.")
        result[key] = entry
    return result


def p_removal_by_crop(workspace):
    """P removal per crop (kg/ha/yr) from the P-FLUX rotation-year rows.
    First averaged within each system, then the median across systems; n and range are recorded."""
    path = Path(workspace) / "data/raw/pflux/v1/PBudgetData.csv"
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    out = {}
    for crop, names in PFLUX_CROPS.items():
        per_system = defaultdict(list)
        for row in rows:
            if row["Crop names"].strip() in names and not row["Rotation year"].startswith("System"):
                try:
                    value = float(row["Annual average P removed by crop (kg/ha)"])
                except ValueError:
                    continue
                per_system[row["Cropping system ID"]].append(value)
        means = [sum(v) / len(v) for v in per_system.values()]
        if means:
            out[crop] = {"kg_p_per_ha": median(means), "systems": len(means), "min": min(means), "max": max(means),
                         "source": "P-FLUX (Williams et al. 2021), median of system means; P removal varies with yield"}
    return out


def nass_request(series, region, years, level):
    args = {"short_desc": series, "agg_level_desc": level, "state_alpha": region["state_alpha"],
            "year__GE": str(years[0]), "year__LE": str(years[1]), "source_desc": "SURVEY", "format": "JSON"}
    if level == "COUNTY":
        args["county_name"] = region["county_name"]
    if "PRICE RECEIVED" in series:
        args["reference_period_desc"] = "MARKETING YEAR"
        args["freq_desc"] = "ANNUAL"
    return args


def parse_nass(payload, series):
    if "error" in payload:
        raise ValueError(f"NASS Quick Stats error: {payload['error']}")
    values = {}
    for row in payload.get("data", []):
        if row.get("short_desc") != series:
            raise ValueError("The NASS response series does not match the request.")
        raw = str(row.get("Value", "")).strip()
        if raw.startswith("("):
            continue
        year = int(row["year"])
        if year in values:
            raise ValueError(f"Year {year} appears twice in the NASS response.")
        values[year] = float(raw.replace(",", ""))
    return values


def nass_fetch(workspace, args, key, online=False, label="NASS"):
    """Cached Quick Stats request (raw JSON). The API key is added to the URL but never written to the receipt or the cache key."""
    public_url = "https://quickstats.nass.usda.gov/api/api_GET/?" + urllib.parse.urlencode(args)
    cache_key = hashlib.sha256(public_url.encode()).hexdigest()[:24]
    folder = Path(workspace) / "data/raw/nass"
    path, receipt_path = folder / f"{cache_key}.json", folder / f"{cache_key}.receipt.json"
    if path.is_file() and receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("url") != public_url or receipt.get("sha256") != digest(path):
            raise ValueError("NASS cache URL/SHA-256 mismatch.")
        return json.loads(path.read_bytes()), {**receipt, "transfer": "cached"}
    if not online:
        raise ValueError(f"{label} query not in cache; needs --online and FIELDSHIFT_NASS_KEY.")
    if not key:
        raise ValueError("No NASS API key. Free key: https://quickstats.nass.usda.gov/api — put it in the FIELDSHIFT_NASS_KEY environment variable.")
    raw = request_bytes(public_url + "&" + urllib.parse.urlencode({"key": key}), 32 * 1024 * 1024)
    payload = json.loads(raw)
    if "error" in payload and "no data" not in str(payload["error"]).lower():
        raise ValueError(f"NASS Quick Stats error: {payload['error']}")
    folder.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder, delete=False, suffix=".part") as stream:
            temporary = Path(stream.name)
            stream.write(raw)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    receipt = {"url": public_url, "sha256": digest(path), "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
               "source": "USDA NASS Quick Stats", "series": args.get("short_desc"), "level": args.get("agg_level_desc")}
    atomic_json(receipt_path, receipt)
    return payload, {**receipt, "transfer": "downloaded"}


def nass_series(workspace, series, region, years, level, key, online=False):
    payload, receipt = nass_fetch(workspace, nass_request(series, region, years, level), key, online)
    return parse_nass(payload, series), receipt


def nass_inputs(workspace, config, online=False, key=None):
    """Yield (county first, else state) and state price averages per region × crop. NASS has no costs."""
    key = key if key is not None else os.environ.get("FIELDSHIFT_NASS_KEY")
    nass = config.get("nass", {})
    years = nass.get("years", [2014, 2023])
    result, provenance, problems = {}, [], []
    for region_id, region in nass.get("regions", {}).items():
        for crop in config["allowed_crops"].get(region_id, []):
            spec = NASS_SERIES.get(crop)
            if spec is None:
                continue
            entry = {"yield": None, "unit": spec["unit"], "price": None, "cost": None, "yield_source": "",
                     "price_source": "", "cost_source": "", "source_years": f"{years[0]}-{years[1]}", "origin": "nass"}
            for level in (("COUNTY", "STATE") if region.get("county_name") else ("STATE",)):
                try:
                    values, receipt = nass_series(workspace, spec["yield"], region, years, level, key, online)
                except ValueError as error:
                    problems.append(f"{region_id}/{crop} verim ({level}): {error}")
                    continue
                provenance.append(receipt)
                if values:
                    entry["yield"] = sum(values.values()) / len(values)
                    entry["yield_source"] = f"USDA NASS Quick Stats, {level} {len(values)}-year mean: {spec['yield']}"
                    break
            try:
                values, receipt = nass_series(workspace, spec["price"], region, years, "STATE", key, online)
                provenance.append(receipt)
                if values:
                    entry["price"] = sum(values.values()) / len(values) * spec["price_factor"]
                    entry["price_source"] = f"USDA NASS Quick Stats, STATE {len(values)}-year mean: {spec['price']}" + (
                        f"; {NASS_NOTE}" if spec["price_factor"] != 1 else "")
            except ValueError as error:
                problems.append(f"{region_id}/{crop} fiyat: {error}")
            result[(region_id, crop)] = entry
    return result, provenance, problems


def merge_inputs(nass, manual):
    """A sourced manual value overrides the NASS value; merged field by field."""
    merged = {}
    for key in set(nass) | set(manual):
        base = dict(nass.get(key, {}))
        for field in ("yield", "price", "cost"):
            if manual.get(key, {}).get(field) is not None:
                base[field] = manual[key][field]
                base[f"{field}_source"] = manual[key][f"{field}_source"]
        if manual.get(key, {}).get("unit"):
            base.setdefault("unit", manual[key]["unit"])
        merged[key] = base
    return merged


def year_profit(region, crop, previous, inputs, config, p_removal, price_factor=1.0):
    """Profit for one year (USD/acre) and the missing inputs."""
    if crop == "Fallow/Idle Cropland":
        cost = config.get("fallow_cost_usd_per_acre")
        return (None, ["fallow cost"]) if cost is None else (-float(cost), [])
    entry = inputs.get((region, crop), {})
    missing = [f"{crop} {label}" for field, label in (("yield", "yield"), ("price", "price"), ("cost", "cost"))
               if entry.get(field) is None]
    p_price = config.get("p_fertilizer_price_usd_per_kg_p")
    if p_price is None:
        missing.append("P fertilizer price")
    if crop not in p_removal:
        missing.append(f"{crop} P removal")
    if missing:
        return None, missing
    multiplier = 1.0
    for effect in config.get("rotation_effects", []):
        if effect["previous"] == previous and effect["crop"] == crop and effect.get("region", region) == region:
            multiplier *= effect["yield_multiplier"]
    p_cost = p_removal[crop]["kg_p_per_ha"] / ACRES_PER_HA * float(p_price)
    return entry["yield"] * multiplier * entry["price"] * price_factor - entry["cost"] - p_cost, []


FALLOW = "Fallow/Idle Cropland"


def years_without_fallow(sequence):
    """Number of consecutive years without fallow at the end of the sequence."""
    count = 0
    for crop in reversed(sequence):
        if crop == FALLOW:
            break
        count += 1
    return count


def valid_sequence(sequence, config, min_wheat, feasible, region=None, initial_run=0):
    run = 1
    for a, b in zip(sequence, sequence[1:]):
        run = run + 1 if a == b else 1
        if run > config["max_consecutive_same_crop"]:
            return False
    if sum(c in WHEAT_CROPS for c in sequence) < min_wheat:
        return False
    rule = config.get("fallow_requirement", {}).get(region) if region else None
    if rule:
        limit, streak = rule["max_years_without_fallow"], initial_run
        for crop in sequence:
            streak = 0 if crop == FALLOW else streak + 1
            if streak > limit:
                return False
    return all(feasible(a, b, i + 1) for i, (a, b) in enumerate(zip(sequence, sequence[1:])))


def evaluate(region, sequence, inputs, config, p_removal, previous=None, price_factor=1.0):
    total, missing, yearly, p_total = 0.0, [], [], 0.0
    for i, crop in enumerate(sequence):
        profit, gaps = year_profit(region, crop, previous if i == 0 else sequence[i - 1], inputs, config, p_removal, price_factor)
        removal = p_removal.get(crop, {}).get("kg_p_per_ha") if crop != "Fallow/Idle Cropland" else 0.0
        yearly.append({"crop": crop, "profit_usd_per_acre": profit, "p_removal_kg_per_ha": removal, "missing": gaps})
        missing.extend(g for g in gaps if g not in missing)
        total = None if profit is None or total is None else total + profit
        p_total = None if removal is None or p_total is None else p_total + removal
    return {"sequence": list(sequence), "total_profit_usd_per_acre": total, "cumulative_p_removal_kg_per_ha": p_total,
            "yearly": yearly, "missing_inputs": missing}


def optimize(region, crops, inputs, config, p_removal, previous=None, feasible=lambda a, b, i: True, initial_run=0, price_factor=1.0):
    """Enumerates every valid sequence (at most 8 years, 6 crops) and ranks them by profit."""
    years = config["years"]
    if len(crops) ** years > 2_000_000:
        raise ValueError("Crop × year combinations exceed the exhaustive-search limit.")
    evaluated, incomplete = [], set()
    memo = {}
    original = year_profit

    def cached(region_, crop, prev, inputs_, config_, p_removal_, factor=1.0):
        key = (crop, prev, factor)
        if key not in memo:
            memo[key] = original(region_, crop, prev, inputs_, config_, p_removal_, factor)
        return memo[key]
    globals()["year_profit"] = cached
    try:
        return _optimize_loop(region, crops, years, inputs, config, p_removal, previous, feasible, initial_run, price_factor, evaluated, incomplete)
    finally:
        globals()["year_profit"] = original


def _optimize_loop(region, crops, years, inputs, config, p_removal, previous, feasible, initial_run, price_factor, evaluated, incomplete):
    for sequence in itertools.product(crops, repeat=years):
        if not valid_sequence(sequence, config, config.get("min_wheat_seasons", 0), feasible, region, initial_run):
            continue
        result = evaluate(region, sequence, inputs, config, p_removal, previous, price_factor)
        if result["total_profit_usd_per_acre"] is None:
            incomplete.update(result["missing_inputs"])
            continue
        evaluated.append(result)
    evaluated.sort(key=lambda r: (-r["total_profit_usd_per_acre"], r["sequence"]))
    return evaluated, sorted(incomplete)
