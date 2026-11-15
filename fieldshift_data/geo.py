"""State lookup: point-in-polygon test on US Census 2017 boundaries (assets/us_states.json, EPSG:4326)."""

import json
from functools import lru_cache
from pathlib import Path

FIPS = {"01": "AL", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA",
        "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA",
        "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
        "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
        "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}
NAMES = {"KS": "Kansas", "NE": "Nebraska", "SD": "South Dakota", "ND": "North Dakota", "OK": "Oklahoma", "TX": "Texas",
            "CO": "Colorado", "MN": "Minnesota", "IA": "Iowa", "MO": "Missouri", "MT": "Montana", "WY": "Wyoming", "NM": "New Mexico"}


@lru_cache(maxsize=1)
def states():
    data = json.loads((Path(__file__).resolve().parent / "assets/us_states.json").read_text(encoding="utf-8"))
    out = []
    for f in data["features"]:
        polys = f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiPolygon" else [f["geometry"]["coordinates"]]
        out.append((FIPS.get(f["id"]), f["properties"]["name"], polys))
    return out


def _in_ring(lon, lat, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def state_of(lon, lat):
    """Postal code of the point's state; None outside the boundaries."""
    for code, _, polys in states():
        for poly in polys:
            if _in_ring(lon, lat, poly[0]) and not any(_in_ring(lon, lat, hole) for hole in poly[1:]):
                return code
    return None
