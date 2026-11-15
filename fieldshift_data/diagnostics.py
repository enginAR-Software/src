"""Live smoke test uses an empty temporary cache, never bundled observations."""

from datetime import date, datetime, timezone
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from . import __version__
from . import alignment
from .catalog import SOURCES, source_directory
from .climate import get as get_climate
from .download import fetch, validate_cache
from .pipeline import run as data_run
from .planning import run as plan_run
from .tables import write_json
from .cropland import grid
from .cropland_source import cached_json, parse_service, parse_classes, parse_raster, samples
from .tables import read_zip_csv


def run(workspace, online=False):
    workspace = Path(workspace).resolve()
    output = workspace / "outputs" / ("selftest_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:8])
    output.mkdir(parents=True)
    report = {"software_version": __version__, "mode": "live_network_empty_cache" if online else "offline_copy",
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "status": "running", "checks": []}
    write_json(output / "SELF_TEST.json", report)

    def check(name, function):
        print(f"Kontrol: {name}", flush=True)
        try:
            evidence = function()
            report["checks"].append({"name": name, "status": "passed", "evidence": evidence})
            return True
        except Exception as error:
            report["checks"].append({"name": name, "status": "failed", "error_type": type(error).__name__, "error": str(error)})
            return False
        finally:
            write_json(output / "SELF_TEST.json", report)

    with tempfile.TemporaryDirectory(prefix="fieldshift-real-data-test-") as temporary:
        isolated = Path(temporary)
        ready = {}
        for key in SOURCES:
            def acquire(key=key):
                if online:
                    result = fetch(isolated, key)
                    if result["acquisition"]["downloaded_count"] != len(SOURCES[key]["files"]):
                        raise ValueError("Not all expected files were downloaded into the empty cache.")
                    return result
                validate_cache(workspace, key)
                shutil.copytree(source_directory(workspace, key), source_directory(isolated, key))
                return validate_cache(isolated, key)
            ready[key] = check(f"{key}: {'real download' if online else 'local verification'}", acquire)
        if all(ready.values()):
            def pipeline():
                _, metrics = data_run(isolated, with_analysis=True)
                if metrics["pflux"]["systems"] != 61 or metrics["napeshm"]["soil_plots"] != 1453 or metrics["pilot_analysis"]["selected_plots"] != 36:
                    raise ValueError("Expected row counts of the sources do not match.")
                return metrics
            check("preprocessing and pilot analysis from real files", pipeline)
            def planning():
                config = Path(__file__).resolve().parent.parent / "config/planning.json"
                _, result = plan_run(isolated, config)
                if not result["best"] or result["best"][0]["system_id"] != "AAFC-Sys1":
                    raise ValueError("The reference planning scenario did not produce the expected solution.")
                best = result["best"][0]
                if abs(best["final_cumulative_p_change"] - 19) > 1e-8:
                    raise ValueError("P accounting of the reference plan does not match.")
                return {"system_id": best["system_id"], "schedule": best["schedule"], "feasible_scenarios": result["feasible_scenarios"]}
            check("six-season plan from real rotations", planning)
        else:
            report["checks"].append({"name": "data pipeline and planning", "status": "skipped", "reason": "A required source could not be downloaded/verified."})
        if online and ready.get("napeshm"):
            for kind, year in (("historical", 2024), ("projection", 2027)):
                def climate(kind=kind, year=year):
                    rows, receipt, transfer = get_climate(isolated, "USOR03", date(year, 1, 1), date(year, 1, 7), kind, "ssp245", True)
                    if transfer != "downloaded" or len(rows) != 7:
                        raise ValueError("The real climate download could not be verified.")
                    if any(any(row[p] is None for p in ("T2M", "PRECTOTCORR")) for row in rows):
                        raise ValueError("The live-test climate response contains missing values.")
                    return {"request": receipt["request"], "sha256": receipt["sha256"], "api_header": receipt["api_header"], "day_count": len(rows), "transfer": transfer}
                check(f"NASA POWER {kind}: real HTTPS download", climate)
        if ready.get("napeshm"):
            def align():
                if not online and (workspace / "data/raw/nasa_power").exists():
                    shutil.copytree(workspace / "data/raw/nasa_power", isolated / "data/raw/nasa_power", dirs_exist_ok=True)
                _, result = alignment.run(isolated, online=online)
                if result["source_seasons"] != 26 or result["aligned_soil_plots"] != 12 or result["unlinked_soil_plots"] != 24:
                    raise ValueError("Source season/date alignment does not match the expected observation coverage.")
                if result["dynamic_soil_model_ready"]:
                    raise ValueError("A dynamic model was treated as ready from single-campaign data.")
                return result
            check("same site/season/sampling date alignment", align)
            def crops():
                if not online and (workspace / "data/raw/cropland_cros").exists():
                    shutil.copytree(workspace / "data/raw/cropland_cros", isolated / "data/raw/cropland_cros")
                tables = read_zip_csv(source_directory(isolated, "napeshm") / "NAPESHM_public_dataset_06032024.zip")
                site = next(r for r in tables["sites"].rows if r["sitecode"] == "USOR03")
                receipts = []
                _, receipt = cached_json(isolated, "", {}, parse_service, online)
                receipts.append(receipt)
                _, receipt = cached_json(isolated, "rasterAttributeTable", {}, parse_classes, online)
                receipts.append(receipt)
                raster, receipt = cached_json(isolated, "query", {"where": "Year = 2019 AND Category = 1",
                                              "outFields": "OBJECTID,Name,Year", "returnGeometry": "false"},
                                              lambda payload: parse_raster(payload, 2019), online)
                receipts.append(receipt)
                rows, receipt = samples(isolated, grid(site, 5, .01), 2019, raster["OBJECTID"], online)
                receipts.append(receipt)
                center = next(r for r in rows if r["is_center"])
                if len(rows) != 25 or center["cdl_code"] != 24 or online and any(r["transfer"] != "downloaded" for r in receipts):
                    raise ValueError("The CDL real classification/download check does not match.")
                return {"sample_count": len(rows), "year": 2019, "center_code": center["cdl_code"],
                        "center_class": "Winter Wheat", "provenance": receipts}
            check("USDA CDL: crop classification and source year", crops)
    report["status"] = "passed" if report["checks"] and all(c["status"] == "passed" for c in report["checks"]) else "failed"
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(output / "SELF_TEST.json", report)
    lines = ["# FieldShift download and data-use test", "", f"Mode: {report['mode']}; result: {report['status']}.", "",
             "Live mode downloads into an empty temporary folder without using existing raw files. Temporary data are removed at the end; DOI, version, SHA-256 and API details stay in the JSON record.", "",
             "| Check | Result |", "|---|---|"]
    lines += [f"| {r['name']} | {r['status']} |" for r in report["checks"]]
    for r in report["checks"]:
        if r["status"] == "failed":
            lines += ["", f"Hata — {r['name']}: {r['error']}"]
    (output / "SELF_TEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output, report
