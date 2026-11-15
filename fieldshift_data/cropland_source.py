"""Bounded, reproducible reads from the public USDA CroplandCROS service."""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import tempfile
from urllib.parse import urlencode

from .download import atomic_json, request_bytes
from .tables import digest


BASE = "https://pdi.scinet.usda.gov/image/rest/services/CDL_WM/ImageServer"
WHEAT_CLASSES = {22: "Durum Wheat", 23: "Spring Wheat", 24: "Winter Wheat",
                 26: "Dbl Crop WinWht/Soybeans", 225: "Dbl Crop WinWht/Corn",
                 230: "Dbl Crop Lettuce/Durum Wht", 234: "Dbl Crop Durum Wht/Sorghum",
                 236: "Dbl Crop WinWht/Sorghum", 238: "Dbl Crop WinWht/Cotton"}


def cached_json(workspace, operation, args, validator, online=False):
    if operation not in ("", "query", "rasterAttributeTable", "getSamples"):
        raise ValueError("Unsupported CDL operation.")
    url = BASE + ("/" + operation if operation else "") + "?" + urlencode({"f": "json", **args})
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    folder = Path(workspace) / "data/raw/cropland_cros"
    path, receipt_path = folder / f"{key}.json", folder / f"{key}.receipt.json"
    receipt = None
    if path.exists() or receipt_path.exists():
        if not path.is_file() or not receipt_path.is_file():
            raise ValueError("CDL cache incomplete; move the file aside and download again.")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("url") != url or receipt.get("sha256") != digest(path):
            raise ValueError("CDL cache URL/SHA-256 mismatch; not overwritten.")
        raw = path.read_bytes()
    else:
        if not online:
            raise ValueError("CDL request not in cache; use cropland --online for the first download.")
        raw = request_bytes(url, 4 * 1024 * 1024)
    payload = json.loads(raw)
    if "error" in payload:
        raise ValueError(f"USDA CDL service error: {payload['error']}")
    parsed = validator(payload)
    if receipt is not None:
        return parsed, {**receipt, "transfer": "cached"}
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
    receipt = {"url": url, "operation": operation or "service_metadata", "sha256": digest(path),
               "bytes": len(raw), "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
               "source": "USDA NASS Cropland Data Layer / CroplandCROS"}
    atomic_json(receipt_path, receipt)
    return parsed, {**receipt, "transfer": "downloaded"}


def parse_service(payload):
    if payload.get("name") != "CDL_WM" or payload.get("bandCount") != 1 or payload.get("serviceDataType") != "esriImageServiceDataTypeThematic":
        raise ValueError("Not the expected single-band CDL classification service.")
    if not {"Year", "OBJECTID", "Category"} <= {f["name"] for f in payload["fields"]}:
        raise ValueError("The CDL catalog schema has changed.")
    return payload


def parse_classes(payload):
    classes = {}
    for feature in payload["features"]:
        item = feature["attributes"]
        code, label = item["Value"], item["Class_Names"]
        if type(code) is not int or not 0 <= code <= 255 or code in classes:
            raise ValueError("CDL class code invalid or duplicated.")
        classes[code] = label
    if any(classes.get(code) != label for code, label in WHEAT_CLASSES.items()):
        raise ValueError("The USDA wheat code dictionary does not match the expected definitions.")
    return classes


def parse_raster(payload, year):
    features = payload["features"]
    if payload.get("exceededTransferLimit") or len(features) != 1:
        raise ValueError(f"{year}: no single, complete annual CDL raster record found.")
    item = features[0]["attributes"]
    if item["Year"] != year or type(item["OBJECTID"]) is not int or not item.get("Name"):
        raise ValueError("CDL catalog year or id does not match.")
    return item


def parse_samples(payload, points, year, raster_id):
    matched = {}
    for sample in payload["samples"]:
        if sample["rasterId"] != raster_id or sample["attributes"]["Year"] != year:
            raise ValueError("Year or raster id of the CDL sample does not match the request.")
        location = sample["location"]
        if location["spatialReference"].get("latestWkid", location["spatialReference"].get("wkid")) != 4326:
            raise ValueError("CDL sample coordinate system is not EPSG:4326.")
        candidates = [p for p in points if abs(p["longitude"] - location["x"]) < 1e-7 and abs(p["latitude"] - location["y"]) < 1e-7]
        if len(candidates) != 1 or candidates[0]["point_id"] in matched:
            raise ValueError("CDL sample location unknown or duplicated.")
        resolution = sample.get("resolution")
        if not isinstance(resolution, (int, float)) or not math.isfinite(resolution) or resolution <= 0:
            raise ValueError("Invalid resolution information in the CDL sample.")
        raw = sample["value"]
        if raw is None or str(raw).strip().casefold() in ("nodata", "no data", ""):
            code, status = None, "nodata"
        else:
            try:
                code = int(str(raw))
            except ValueError as error:
                raise ValueError("CDL sample is not a single integer class code.") from error
            if not 0 <= code <= 255:
                raise ValueError("CDL class code outside 0–255.")
            status = "background" if code == 0 else "classified"
            if code == 0:
                code = None
        matched[candidates[0]["point_id"]] = {"cdl_code": code, "status": status,
                                               "source_resolution": resolution}
    return [{**p, "year": year, "raster_id": raster_id,
             **matched.get(p["point_id"], {"cdl_code": None, "status": "sample_missing", "source_resolution": None})}
            for p in points]


def samples(workspace, points, year, raster_id, online=False):
    args = {"geometryType": "esriGeometryMultipoint",
            "geometry": json.dumps({"points": [[p["longitude"], p["latitude"]] for p in points],
                                    "spatialReference": {"wkid": 4326}}, separators=(",", ":")),
            "mosaicRule": json.dumps({"mosaicMethod": "esriMosaicLockRaster", "lockRasterIds": [raster_id],
                                      "where": f"Year = {year}"}, separators=(",", ":")),
            "returnFirstValueOnly": "true", "interpolation": "RSP_NearestNeighbor", "outFields": "Year,Name,OBJECTID"}
    return cached_json(workspace, "getSamples", args, lambda payload: parse_samples(payload, points, year, raster_id), online)
