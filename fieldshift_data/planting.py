"""Component E: planting date window per crop for every plan year.

Rules live in config/crop_calendar.json, with the source of every threshold.
Input is the NASA POWER NEX-GDDP daily projection (packaged cache or --online).
A computation with missing days gives no result; the status becomes "missing_data".
"""

from datetime import date, timedelta
import json
from pathlib import Path
from statistics import fmean

from . import climate

PERIOD_CHUNKS = {"baseline": [(2015, 2019), (2020, 2024)], "future": [(2040, 2044), (2045, 2049)]}
SINGLE_YEARS = (2027,)


def validate_calendar(calendar):
    crops = calendar.get("crops")
    if not isinstance(crops, dict) or not crops:
        raise ValueError("The crop calendar contains no crop rules.")
    for name, rule in crops.items():
        kind = rule.get("type")
        if kind not in ("spring", "winter", "none"):
            raise ValueError(f"{name}: rule type must be spring, winter or none.")
        if not isinstance(rule.get("sources"), dict) or not rule["sources"]:
            raise ValueError(f"{name}: every rule needs a source description.")
        if kind == "spring":
            for key in ("start_threshold_c", "mean_days", "persist_days"):
                if not isinstance(rule.get(key), (int, float)):
                    raise ValueError(f"{name}: {key} must be a number.")
            if (rule.get("season_days") is None) != (rule.get("season_base_c") is None):
                raise ValueError(f"{name}: season_days and season_base_c must be given together.")
        if kind == "winter":
            for key in ("gdd_base_c", "gdd_by_dec31_c", "early_days"):
                if not isinstance(rule.get(key), (int, float)):
                    raise ValueError(f"{name}: {key} must be a number.")


def load_calendar(path):
    calendar = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_calendar(calendar)
    return calendar


def series(rows):
    """date -> T2M (None korunur)."""
    return {date.fromisoformat(r["date"]): r["T2M"] for r in rows}


def load_site_daily(workspace, site, scenario="ssp245", online=False, fetch=None):
    """Loads the daily projection using the packaged chunk layout; a missing chunk is skipped and recorded."""
    fetch = fetch or (lambda s, a, b: climate.get(workspace, s, a, b, "projection", scenario, online)[0])
    daily, missing_chunks = {}, []
    chunks = [c for period in PERIOD_CHUNKS.values() for c in period] + [(y, y) for y in SINGLE_YEARS]
    for first, last in chunks:
        try:
            daily.update(series(fetch(site, date(first, 1, 1), date(last, 12, 31))))
        except ValueError:
            missing_chunks.append(f"{first}-{last}")
    return daily, missing_chunks


def running_mean(daily, day, days):
    values = [daily.get(day - timedelta(days=i)) for i in range(days)]
    return None if any(v is None for v in values) else fmean(values)


def spring_window(daily, year, rule):
    """Start: first day after 1 March when the n-day mean crosses the threshold and stays above it.
    End: the day the 7-day mean falls below the season base in autumn, minus the season length."""
    threshold, n, persist = rule["start_threshold_c"], int(rule["mean_days"]), int(rule["persist_days"])
    month, dom = (int(x) for x in rule.get("search_from", "03-01").split("-"))
    first = day = date(year, month, dom)
    last = date(year, 7, 31)
    start = None
    while day <= last:
        window = [running_mean(daily, day + timedelta(days=k), n) for k in range(persist)]
        if any(v is None for v in window):
            return {"status": "missing_data", "start": None, "end": None, "detail": f"Missing days around {day.isoformat()}"}
        if all(v >= threshold for v in window):
            start = day
            if day == first:
                return {"status": "no_window", "start": None, "end": None,
                        "detail": f"Threshold already exceeded at the search start ({first.isoformat()}); search_from should be earlier"}
            break
        day += timedelta(days=1)
    if start is None:
        return {"status": "no_window", "start": None, "end": None, "detail": "Threshold not crossed persistently by 31 July"}
    if start < date(year, 3, 1):
        return {"status": "low_confidence", "start": start, "end": None,
                "detail": "The temperature threshold is crossed in mid-winter; here planting time is set by soil workability and frost risk. Check with the local calendar."}
    if rule.get("season_days") is None:
        return {"status": "start_only", "start": start, "end": None, "detail": "No source for season length; end not computed"}
    day, cutoff = date(year, 7, 1), None
    while day <= date(year, 12, 31):
        value = running_mean(daily, day, 7)
        if value is None:
            return {"status": "missing_data", "start": start, "end": None, "detail": f"Missing days around the autumn cutoff {day.isoformat()}"}
        if value < rule["season_base_c"]:
            cutoff = day
            break
        day += timedelta(days=1)
    if cutoff is None:
        return {"status": "start_only", "start": start, "end": None, "detail": "Did not fall below the season base within the year"}
    end = cutoff - timedelta(days=int(rule["season_days"]))
    if end < start:
        return {"status": "no_window", "start": start, "end": end, "detail": "The season length does not fit into the warm period"}
    return {"status": "ok", "start": start, "end": end, "detail": f"Sonbahar kesimi {cutoff.isoformat()}"}


def winter_window(daily, harvest_year, rule):
    """Winter wheat: the CDL year is the harvest year; sowing is in the previous autumn.
    Latest sowing = last day whose cumulative GDD to 31 December meets the threshold; earliest = latest − early_days."""
    sow_year = harvest_year - 1
    base, need = rule["gdd_base_c"], rule["gdd_by_dec31_c"]
    end_of_year = date(sow_year, 12, 31)
    days = [date(sow_year, 8, 1) + timedelta(days=i) for i in range((end_of_year - date(sow_year, 8, 1)).days + 1)]
    allowed = int(rule.get("max_missing_late_december_days", 0))
    missing = [d for d in days if daily.get(d) is None]
    if missing and (len(missing) > allowed or any(d < date(sow_year, 12, 20) for d in missing)):
        return {"status": "missing_data", "start": None, "end": None, "detail": f"{sow_year} August–December days missing ({len(missing)} days)"}
    cumulative, latest = 0.0, None
    for d in reversed(days):
        if daily.get(d) is None:
            continue
        cumulative += max(daily[d] - base, 0.0)
        if cumulative >= need:
            latest = d
            break
    if latest is None:
        return {"status": "no_window", "start": None, "end": None, "detail": "The GDD threshold is not met even when sown on 1 August"}
    note = f"; {len(missing)} late-December days could not be added to GDD (no data); the window may be slightly early" if missing else ""
    return {"status": "ok", "start": latest - timedelta(days=int(rule["early_days"])), "end": latest,
            "detail": f"Sown in autumn {sow_year}; harvest year {harvest_year}{note}"}


def climatology(daily, years):
    """Day-of-year mean (29 February dropped): doy -> (mean, number of years, total years)."""
    years = list(years)
    out = {}
    for doy in range(365):
        d0 = date(2001, 1, 1) + timedelta(days=doy)
        values = [daily[d0.replace(year=y)] for y in years if daily.get(d0.replace(year=y)) is not None]
        out[doy] = (fmean(values) if values else None, len(values), len(years))
    return out


def synthetic_year(clim, year, min_fraction=0.8):
    """Places normals into the requested calendar year (in leap years 29 February copies 28 February).
    Days whose year coverage is below min_fraction are left empty."""
    result = {}
    for doy, (mean, count, total) in clim.items():
        d = (date(2001, 1, 1) + timedelta(days=doy)).replace(year=year)
        value = mean if count and count >= min_fraction * total else None
        result[d] = value
        if d.month == 2 and d.day == 28:
            try:
                result[date(year, 2, 29)] = value
            except ValueError:
                pass
    return result


def normal_for_year(daily, calendar_year, cache, min_fraction=0.8):
    """Places the nearest 10-year model normal into the requested calendar year.
    For winter wheat min_fraction is lowered because of systematic late-December gaps in NEX-GDDP;
    the number of days computed from few years is written into the description."""
    period = (2015, 2024) if abs(calendar_year - 2020) <= abs(calendar_year - 2045) else (2040, 2049)
    if period not in cache:
        cache[period] = climatology(daily, range(period[0], period[1] + 1))
    clim = cache[period]
    low = sum(1 for mean, count, total in clim.values() if mean is not None and count < 0.8 * total)
    basis = f"NASA projection normal {period[0]}–{period[1]}"
    if min_fraction < 0.8 and low:
        basis += f"; {low} days (late December) from fewer than 80% of years"
    return synthetic_year(clim, calendar_year, min_fraction), basis


def window(daily, crop, year, calendar, cache=None):
    """The real daily projection of that year is tried first; if absent or incomplete, the nearest normal is used."""
    cache = {} if cache is None else cache
    rule = calendar["crops"].get(crop)
    if rule is None:
        return {"crop": crop, "plan_year": year, "status": "no_rule", "start": None, "end": None,
                "basis": None, "detail": "No planting rule configured for this crop"}
    if rule["type"] == "none":
        return {"crop": crop, "plan_year": year, "status": "no_planting", "start": None, "end": None,
                "basis": None, "detail": rule["sources"].get("note", "No planting this year")}
    compute = spring_window if rule["type"] == "spring" else winter_window
    calendar_year = year if rule["type"] == "spring" else year - 1
    result, basis = None, None
    if sum(d.year == calendar_year for d in daily) >= 300:
        result, basis = compute(daily, year, rule), f"NASA projection {calendar_year}"
        if result["status"] == "missing_data":
            basis_note = result["detail"]
            result = None
    if result is None:
        data, basis = normal_for_year(daily, calendar_year, cache, 0.8 if rule["type"] == "spring" else 0.01)
        result = compute(data, year, rule)
        if sum(d.year == calendar_year for d in daily) >= 300:
            basis += f" (actual year incomplete: {basis_note})"
    return {"crop": crop, "plan_year": year, "status": result["status"],
            "start": result["start"].isoformat() if result["start"] else None,
            "end": result["end"].isoformat() if result["end"] else None,
            "basis": basis, "detail": result["detail"]}
