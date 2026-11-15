"""Satellite indicator: MODIS MOD13Q1 NDVI (250 m, 16-day) — ORNL DAAC MODIS Web Service.

For each parcel point, the NDVI curve of the chosen year is downloaded and the following are derived:
    * peak NDVI and peak date, green-up / senescence dates (half-amplitude threshold),
    * bare-soil time (16-day periods with NDVI < 0.25),
    * phenology consistency: does the peak month match the typical peak months of the crop CDL reports for that year?
So the satellite (1) independently checks the CDL crop label and (2) shows whether the planting-window computation
is consistent with observed plant growth.

Service: https://modis.ornl.gov/rst/api/v1/ (no key needed; at most 10 MODIS dates per request).
Product: MOD13Q1 v061, band 250m_16_days_NDVI, scale 0.0001 (Didan 2021, doi:10.5067/MODIS/MOD13Q1.061).
"""

import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import time
import urllib.parse
from uuid import uuid4

from .download import atomic_json, request_bytes
from .tables import digest, write_csv, write_json

BASE = "https://modis.ornl.gov/rst/api/v1/MOD13Q1/subset"
BAND = "250m_16_days_NDVI"
SCALE = 0.0001
BARE = 0.25
CHUNK = 10
PHENOLOGY_PATH = Path(__file__).resolve().parent.parent / "config" / "phenology.json"


def modis_dates(year):
    """MOD13Q1 16-day composites start on day 1 every year: 001, 017, …, 353 (23 dates)."""
    return [f"A{year}{doy:03d}" for doy in range(1, 366, 16)]


def calendar(modis_date):
    year, doy = int(modis_date[1:5]), int(modis_date[5:])
    return date(year, 1, 1) + timedelta(days=doy - 1)


def request_url(lat, lon, first, last):
    return BASE + "?" + urllib.parse.urlencode({"latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}", "band": BAND,
                                                "startDate": first, "endDate": last, "kmAboveBelow": 0, "kmLeftRight": 0})


def parse(payload):
    """{modis_date: NDVI} — single pixel; fill values (< -0.2) are skipped."""
    out = {}
    for row in payload.get("subset", []):
        if row.get("band") != BAND:
            continue
        values = [v for v in row.get("data", []) if v is not None]
        if not values:
            continue
        ndvi = values[0] * float(payload.get("scale", SCALE) or SCALE)
        if ndvi >= -0.2:
            out[row["modis_date"]] = round(ndvi, 4)
    return out


def cached(workspace, url, online):
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    folder = Path(workspace) / "data/raw/modis"
    path, receipt_path = folder / f"{key}.json", folder / f"{key}.receipt.json"
    if path.is_file() and receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("url") != url or receipt.get("sha256") != digest(path):
            raise ValueError("MODIS cache URL/SHA-256 mismatch.")
        return json.loads(path.read_bytes()), "cached"
    if not online:
        raise ValueError("MODIS NDVI not in cache; needs satellite --online.")
    raw = request_bytes(url, 4 * 1024 * 1024, {"Accept": "application/json"})
    payload = json.loads(raw)
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
    atomic_json(receipt_path, {"url": url, "sha256": digest(path), "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                               "source": "ORNL DAAC MODIS Web Service, MOD13Q1 v061"})
    time.sleep(0.2)
    return payload, "downloaded"


def series(workspace, lat, lon, year, online=False):
    dates = modis_dates(year)
    out, transfers = {}, []
    for i in range(0, len(dates), CHUNK):
        chunk = dates[i:i + CHUNK]
        payload, transfer = cached(workspace, request_url(lat, lon, chunk[0], chunk[-1]), online)
        out.update(parse(payload))
        transfers.append(transfer)
    return [(calendar(d), out[d]) for d in sorted(out)], transfers


def metrics(points, crop, phenology):
    if len(points) < 6:
        return {"status": "insufficient_data", "observations": len(points)}
    values = [v for _, v in points]
    lo, hi = min(values), max(values)
    peak_date = points[values.index(hi)][0]
    half = lo + 0.5 * (hi - lo)
    above = [d for d, v in points if v >= half]
    bare = sum(v < BARE for v in values) * 16
    rule = phenology.get(crop)
    if rule is None:
        consistency = "no_rule"
    elif rule.get("max_peak_ndvi") is not None:
        consistency = "consistent" if hi <= rule["max_peak_ndvi"] else "inconsistent"
    else:
        consistency = "consistent" if peak_date.month in rule["peak_months"] else "inconsistent"
    return {"status": "ok", "observations": len(points), "peak_ndvi": round(hi, 3), "peak_date": peak_date.isoformat(),
            "min_ndvi": round(lo, 3), "green_up": above[0].isoformat(), "senescence": above[-1].isoformat(),
            "bare_soil_days": bare, "cdl_crop": crop, "phenology_check": consistency}


def latest_goal(workspace):
    for folder in sorted((Path(workspace) / "outputs").glob("goal_*"), reverse=True):
        if (folder / "parcels.geojson").is_file():
            return folder
    return None


def crop_in_year(props, year):
    seq = [c.strip() for c in (props.get("observed_sequence") or "").split("→")]
    span = props.get("observed_years") or ""
    try:
        first, last = (int(x) for x in span.split("-"))
    except ValueError:
        return None
    return seq[year - first] if first <= year <= last and len(seq) == last - first + 1 else None


def run(workspace, year=2023, online=False, max_points=None, kinds=("pilot", "corridor")):
    workspace = Path(workspace).resolve()
    goal = latest_goal(workspace)
    if goal is None:
        raise ValueError("Run goal first (the parcel list is read from parcels.geojson).")
    phenology = json.loads(PHENOLOGY_PATH.read_text(encoding="utf-8"))["crops"]
    features = [f for f in json.loads((goal / "parcels.geojson").read_text(encoding="utf-8"))["features"]
                if f["properties"].get("kind") in kinds]
    if max_points:
        features = features[:max_points]
    series_rows, metric_rows, problems, transfers = [], [], [], []
    for n, f in enumerate(features, 1):
        props = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        print(f"MODIS NDVI: {n}/{len(features)} {props['parcel_id']}", flush=True)
        try:
            points, t = series(workspace, lat, lon, year, online)
        except (ValueError, OSError) as error:
            problems.append(f"{props['parcel_id']}: {error}")
            continue
        transfers += t
        crop = crop_in_year(props, year)
        series_rows += [{"parcel_id": props["parcel_id"], "date": d.isoformat(), "ndvi": v} for d, v in points]
        metric_rows.append({"parcel_id": props["parcel_id"], "region": props["region"], "kind": props.get("kind"),
                            "year": year, **metrics(points, crop, phenology)})
    if not metric_rows:
        raise ValueError("No NDVI curve could be retrieved. " + ("; ".join(problems[:3]) or ""))
    output = workspace / "outputs" / ("satellite_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    write_csv(output / "ndvi_series.csv", series_rows)
    write_csv(output / "ndvi_metrics.csv", metric_rows)
    ok = [m for m in metric_rows if m["status"] == "ok"]
    checked = [m for m in ok if m["phenology_check"] in ("consistent", "inconsistent")]
    agree = sum(m["phenology_check"] == "consistent" for m in checked)
    by_crop = {}
    for m in checked:
        by_crop.setdefault(m["cdl_crop"], [0, 0])
        by_crop[m["cdl_crop"]][0] += m["phenology_check"] == "consistent"
        by_crop[m["cdl_crop"]][1] += 1
    report = {"year": year, "goal_output": goal.name, "parcels": len(features), "curves": len(ok),
              "phenology_agreement": None if not checked else agree / len(checked), "by_crop": by_crop,
              "downloaded": transfers.count("downloaded"), "cached": transfers.count("cached"), "problems": problems[:30],
              "source": "ORNL DAAC MODIS Web Service, MOD13Q1 v061 NDVI (doi:10.5067/MODIS/MOD13Q1.061)"}
    write_json(output / "satellite.json", report)
    lines = ["# Satellite indicator: MODIS NDVI", "", f"Year {year} · NDVI curves for {len(ok)} parcels · source: {report['source']}", "",
             f"**Agreement of CDL labels with satellite phenology:** {agree}/{len(checked)}" + (f" ({100 * agree / len(checked):.0f}%)" if checked else ""), "",
             "| CDL crop | Consistent / checked |", "|---|---|"]
    lines += [f"| {c} | {a}/{t} |" for c, (a, t) in sorted(by_crop.items())]
    lines += ["", "Consistency rules are in `config/phenology.json` (with their sources). A mismatch can mean a CDL classification error, a double crop "
              "or a mixed pixel; a 250 m pixel also sees neighbouring land on small fields.", ""]
    if problems:
        lines += ["## Not retrieved", ""] + [f"- {p}" for p in problems[:30]]
    (output / "SATELLITE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output, report


def latest(workspace):
    """Latest satellite output for the interface: {parcel_id: {"metrics": ..., "series": [[date, ndvi], ...]}}."""
    for folder in sorted((Path(workspace) / "outputs").glob("satellite_*"), reverse=True):
        if not (folder / "ndvi_metrics.csv").is_file():
            continue
        out = {}
        with (folder / "ndvi_metrics.csv").open(encoding="utf-8") as stream:
            for r in csv.DictReader(stream):
                out[r["parcel_id"]] = {"metrics": r, "series": []}
        with (folder / "ndvi_series.csv").open(encoding="utf-8") as stream:
            for r in csv.DictReader(stream):
                if r["parcel_id"] in out:
                    out[r["parcel_id"]]["series"].append([r["date"], float(r["ndvi"])])
        return folder.name, out
    return None, {}
