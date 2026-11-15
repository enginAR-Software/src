"""NASA POWER historical and CMIP6 projection acquisition, kept distinct."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import urllib.parse
from uuid import uuid4

from .catalog import source_directory
from .download import atomic_json, request_bytes, validate_cache
from .tables import digest, numeric, read_zip_csv, write_csv, write_json


PARAMETERS = ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR")


def dates(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def request_definition(site, start, end, kind, scenario):
    if kind not in ("historical", "projection") or start > end or (end - start).days > 1826:
        raise ValueError("Climate request: a valid kind and a date range of at most five years are required.")
    if kind == "projection" and (start.year < 2015 or end.year > 2100 or scenario not in ("ssp126", "ssp245", "ssp370")):
        raise ValueError("Projections need 2015–2100 and a supported SSP scenario.")
    if kind == "historical" and (start.year < 1981 or end >= date.today()):
        raise ValueError("Historical requests must lie between 1981 and fully completed past days.")
    latitude, longitude = numeric(site["site_latitude"]), numeric(site["site_longitude"])
    if latitude is None or longitude is None or not -59.875 <= latitude <= 89.875 or not -179.875 <= longitude <= 179.875:
        raise ValueError("Valid coordinates are required for climate data.")
    args = {"parameters": ",".join(PARAMETERS), "community": "AG", "longitude": longitude,
            "latitude": latitude, "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
            "format": "JSON", "time-standard": "UTC"}
    path = "temporal/daily/point" if kind == "historical" else "projection/daily/point"
    if kind == "projection":
        args.update(scenario=scenario, model="ensemble")
    url = "https://power.larc.nasa.gov/api/" + path + "?" + urllib.parse.urlencode(args)
    return {"sitecode": site["sitecode"], "latitude": latitude, "longitude": longitude,
            "kind": kind, "scenario": scenario if kind == "projection" else None,
            "model": "ensemble" if kind == "projection" else None,
            "start": start.isoformat(), "end": end.isoformat(), "url": url}


def parse(payload, request):
    header = payload["header"]
    if str(header.get("time_standard", "")).casefold() != "utc":
        raise ValueError("Climate response is not in UTC time standard.")
    if request["kind"] == "projection":
        if request["scenario"] not in header.get("scenarios", []) or header.get("model") != request["model"]:
            raise ValueError("Projection scenario or model does not match the request.")
        if "NEXGDDP" not in header.get("sources", []):
            raise ValueError("Expected NEX-GDDP projection source missing.")
    elif header.get("scenarios") or "NEXGDDP" in header.get("sources", []):
        raise ValueError("Got a projection response instead of historical observation/reanalysis.")
    start, end = date.fromisoformat(request["start"]), date.fromisoformat(request["end"])
    if header.get("start") != start.strftime("%Y%m%d") or header.get("end") != end.strftime("%Y%m%d"):
        raise ValueError("The date coverage of the climate response does not match.")
    source = payload["properties"]["parameter"]
    series = {}
    for parameter in PARAMETERS:
        unit = payload["parameters"][parameter]["units"]
        if unit != ("mm/day" if parameter == "PRECTOTCORR" else "C"):
            raise ValueError(f"Beklenmeyen iklim birimi: {parameter} = {unit}")
        series[parameter] = source[parameter][request["scenario"]] if request["kind"] == "projection" else source[parameter]
    fill = header.get("fill_value", -999)
    output = []
    for day in dates(start, end):
        record = {"date": day.isoformat(), "sitecode": request["sitecode"], "kind": request["kind"], "scenario": request["scenario"]}
        for parameter in PARAMETERS:
            raw = series[parameter].get(day.strftime("%Y%m%d"))
            value = numeric(raw)
            if value == fill:
                value = None
            if parameter == "PRECTOTCORR" and value is not None and value < 0:
                raise ValueError("Negative precipitation value.")
            record[parameter] = value
        output.append(record)
    if not any(row["T2M"] is not None for row in output) or not any(row["PRECTOTCORR"] is not None for row in output):
        raise ValueError("Climate response has no usable temperature/precipitation.")
    return output


def summarize(rows):
    def one(records, period):
        temp = [r["T2M"] for r in records if r["T2M"] is not None]
        rain = [r["PRECTOTCORR"] for r in records if r["PRECTOTCORR"] is not None]
        return {"period": period, "requested_days": len(records), "temperature_days": len(temp), "precipitation_days": len(rain),
                "mean_temperature_c": statistics.fmean(temp) if temp else None,
                "precipitation_sum_mm": sum(rain) if len(rain) == len(records) else None,
                "complete_temperature": len(temp) == len(records), "complete_precipitation": len(rain) == len(records)}
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["date"][:7]].append(row)
    return one(rows, rows[0]["date"] + "/" + rows[-1]["date"]), [one(records, period) for period, records in sorted(grouped.items())]


def get(workspace, sitecode, start, end, kind="projection", scenario="ssp245", online=False):
    workspace = Path(workspace).resolve()
    soil_provenance = validate_cache(workspace, "napeshm")
    tables = read_zip_csv(source_directory(workspace, "napeshm") / "NAPESHM_public_dataset_06032024.zip")
    sites = [r for r in tables["sites"].rows if r["sitecode"] == sitecode]
    if len(sites) != 1:
        raise ValueError("NAPESHM source site not found.")
    return fetch_site(workspace, sites[0], start, end, kind, scenario, online, soil_provenance)


def get_point(workspace, point_id, latitude, longitude, start, end, kind="projection", scenario="ssp245",
              online=False, coordinate_source=None):
    """Same cache and validation rules for grid points outside NAPESHM (migration corridor)."""
    site = {"sitecode": point_id, "site_latitude": str(latitude), "site_longitude": str(longitude)}
    return fetch_site(Path(workspace).resolve(), site, start, end, kind, scenario, online,
                      coordinate_source or {"dataset": "corridor_grid"})


def fetch_site(workspace, site, start, end, kind, scenario, online, soil_provenance):
    request = request_definition(site, start, end, kind, scenario)
    key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:24]
    folder = workspace / "data/raw/nasa_power" / kind
    path, receipt_path = folder / f"{key}.json", folder / f"{key}.receipt.json"
    if path.exists() or receipt_path.exists():
        if not path.is_file() or not receipt_path.is_file():
            raise ValueError("Climate cache incomplete; move the files aside and download again.")
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("request") != request or digest(path) != receipt.get("sha256"):
            raise ValueError("Climate cache request or SHA-256 does not match.")
        payload = json.loads(path.read_bytes())
        rows = parse(payload, request)
        transfer = "cached"
    else:
        if not online:
            raise ValueError("This climate request is not in the cache. Use --online for the first download.")
        raw = request_bytes(request["url"], 16 * 1024 * 1024)
        payload = json.loads(raw)
        rows = parse(payload, request)
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
        receipt = {"request": request, "sha256": digest(path), "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                   "api_header": payload["header"], "coordinate_source": soil_provenance,
                   "reported_geometry": payload.get("geometry")}
        atomic_json(receipt_path, receipt)
        transfer = "downloaded"
    return rows, receipt, transfer


def run(workspace, sitecode, start, end, kind="projection", scenario="ssp245", online=False):
    rows, receipt, transfer = get(workspace, sitecode, start, end, kind, scenario, online)
    period, monthly = summarize(rows)
    output = Path(workspace).resolve() / "outputs" / ("climate_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    result = {"request": receipt["request"], "provenance": receipt, "transfer": transfer,
              "period_summary": period, "monthly": monthly,
              "missing_counts": {p: sum(row[p] is None for row in rows) for p in PARAMETERS},
              "dates_with_missing_values": [row["date"] for row in rows if any(row[p] is None for p in PARAMETERS)],
              "notice": "Projections are conditional on scenario/model; they are not forecasts of actual weather or crop yield. Not to be read at parcel scale."}
    write_json(output / "climate.json", result)
    write_csv(output / "daily.csv", rows)
    write_csv(output / "monthly.csv", monthly)
    coordinates = [receipt["request"]["longitude"], receipt["request"]["latitude"]]
    write_json(output / "site_climate.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": coordinates},
         "properties": {"sitecode": sitecode, "kind": kind, "scenario": receipt["request"]["scenario"], **period}}]})
    (output / "CLIMATE_REPORT.md").write_text(
        f"# FieldShift climate data\n\nSite: {sitecode}; kind: {kind}; scenario: {receipt['request']['scenario']}; model: {receipt['request']['model']}.\n\n"
        f"Period: {period['period']}. Requested days: {period['requested_days']}; temperature: {period['temperature_days']}; precipitation: {period['precipitation_days']}.\n\n"
        f"Mean temperature of available days: {period['mean_temperature_c']} °C; period precipitation total: {period['precipitation_sum_mm']} mm. If precipitation is missing, the total is left empty.\n\n"
        "Monthly rows cover only the requested date range; a partial month is not counted as a full month. The future scenario is stored separately from observed weather. On its own this output computes neither wheat suitability nor the soil mineral cycle.\n\n"
        "NASA POWER: https://power.larc.nasa.gov/docs/services/api/projection/\n", encoding="utf-8")
    return output, result
