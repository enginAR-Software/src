"""Local command line entry points; no browser or server required."""

import argparse
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys
import zipfile

from .catalog import SOURCES, selection
from . import __version__
from .download import fetch, validate_cache
from .pipeline import run
from . import alignment, climate, diagnostics, planning, regional, cropland, economics, goal, suitability, dashboard, app, yieldmodel, satellite, demo


def main():
    parser = argparse.ArgumentParser(description="FieldShift: real-data download, analysis, wheat-migration corridor and farmer rotation plans")
    parser.add_argument("--version", action="version", version=f"FieldShiftData {__version__}")
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="Folder for data and outputs (default: the project folder)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="List the pinned data sources")
    for command in ("fetch", "verify", "run"):
        p = commands.add_parser(command, help={"fetch": "Download and verify from the source API (internet)",
                                               "verify": "Verify local raw files (offline)",
                                               "run": "Inspect and preprocess local data and compute the P budget"}[command])
        p.add_argument("--dataset", choices=["all", *SOURCES], default="all")
        if command == "run":
            p.add_argument("--offline", action="store_true", help="run is always offline; accepted for clarity")
    query = commands.add_parser("query", help="Show one P-FLUX system from the results database")
    query.add_argument("database", type=Path)
    query.add_argument("--system", required=True, help="Example: AAFC-Sys1")
    analyze = commands.add_parser("analyze", help="Run the data pipeline and the pilot analysis on individual observations")
    analyze.add_argument("--pilot", choices=["all", "oregon", "kansas"], default="all")
    analyze.add_argument("--config", type=Path, default=None, help="Pilot treatment and comparison configuration")
    analyze.add_argument("--offline", action="store_true", help="Analysis runs offline")
    plan = commands.add_parser("plan", help="Compute a constrained multi-year reference plan from observed rotations")
    plan.add_argument("--config", type=Path, default=Path(__file__).resolve().parent.parent / "config/planning.json")
    plan.add_argument("--date", type=date.fromisoformat, default=None, help="YYYY-MM-DD; filters the plan by year")
    plan_view = commands.add_parser("plan-view", help="Query the computed plan for the year of a date")
    plan_view.add_argument("report", type=Path)
    plan_view.add_argument("--date", type=date.fromisoformat, required=True)
    weather = commands.add_parser("climate", help="NASA POWER historical data or future projection")
    weather.add_argument("--site", default="USOR03")
    weather.add_argument("--kind", choices=["historical", "projection"], default="projection")
    weather.add_argument("--scenario", choices=["ssp126", "ssp245", "ssp370"], default="ssp245")
    weather.add_argument("--start", type=date.fromisoformat, default=date(2027, 1, 1))
    weather.add_argument("--end", type=date.fromisoformat, default=date(2027, 12, 31))
    weather.add_argument("--online", action="store_true", help="Download missing climate requests from NASA")
    testing = commands.add_parser("self-test", help="Real download and data-use test in an empty cache")
    testing.add_argument("--online", action="store_true", help="Real network test; otherwise uses the local source copy only")
    seasons = commands.add_parser("seasons", help="Join source seasons, management, historical weather and soil-sampling dates")
    seasons.add_argument("--pilot", choices=["all", "oregon", "kansas"], default="all")
    seasons.add_argument("--online", action="store_true", help="Download missing season weather from NASA")
    seasons.add_argument("--offline", action="store_true", help="Use only the verified local weather cache")
    region = commands.add_parser("regional", help="Regional climate differences between two periods (same model and scenario)")
    region.add_argument("--config", type=Path, default=Path(__file__).resolve().parent.parent / "config/regional.json")
    region.add_argument("--online", action="store_true", help="Download missing periods from NASA")
    region.add_argument("--offline", action="store_true", help="Use only the verified local cache")
    crops = commands.add_parser("cropland", help="Download real USDA crop classes; match observed crop sequences with climate and soil context")
    crops.add_argument("--config", type=Path, default=Path(__file__).resolve().parent.parent / "config/cropland.json")
    crops.add_argument("--regional-config", type=Path, default=Path(__file__).resolve().parent.parent / "config/regional.json")
    crops.add_argument("--online", action="store_true", help="Download missing USDA and climate queries")
    crops.add_argument("--offline", action="store_true", help="Use only the verified local cache")
    root = Path(__file__).resolve().parent.parent
    target = commands.add_parser("goal", help="Project goal components A–E: yearly crop, planting window, profit and migration corridor per parcel")
    target.add_argument("--economics-config", type=Path, default=root / "config/economics.json")
    target.add_argument("--inputs", type=Path, default=root / "config/economics_inputs.csv")
    target.add_argument("--calendar", type=Path, default=root / "config/crop_calendar.json")
    target.add_argument("--corridor-config", type=Path, default=root / "config/corridor.json")
    target.add_argument("--date", type=date.fromisoformat, default=None, help="YYYY-MM-DD: what each parcel should be planting on this date")
    target.add_argument("--online", action="store_true", help="Download missing NASA/USDA/NASS queries")
    target.add_argument("--offline", action="store_true", help="Local cache only")
    view = commands.add_parser("goal-view", help="Query a computed goal output for a date")
    view.add_argument("output", type=Path, help="outputs/goal_... folder")
    view.add_argument("--date", type=date.fromisoformat, required=True)
    view.add_argument("--parcel", default=None)
    board = commands.add_parser("dashboard", help="Goal dashboard: offline DASHBOARD.html built from a goal output")
    board.add_argument("output", type=Path, nargs="?", default=None, help="outputs/goal_... (default: latest goal output)")
    board.add_argument("--calendar", type=Path, default=root / "config/crop_calendar.json")
    appcmd = commands.add_parser("app", help="Interactive interface: map, parcel plan, date query, farmer priorities (opens in a browser)")
    appcmd.add_argument("output", type=Path, nargs="?", default=None, help="outputs/goal_... (default: latest goal output; runs goal if none)")
    appcmd.add_argument("--economics-config", type=Path, default=root / "config/economics.json")
    appcmd.add_argument("--inputs", type=Path, default=root / "config/economics_inputs.csv")
    appcmd.add_argument("--calendar", type=Path, default=root / "config/crop_calendar.json")
    appcmd.add_argument("--corridor-config", type=Path, default=root / "config/corridor.json")
    appcmd.add_argument("--open", action="store_true", help="Open in the default browser after building")
    corridor = commands.add_parser("corridor", help="Components A+D: wheat suitability model and migration corridor")
    corridor.add_argument("--config", type=Path, default=root / "config/corridor.json")
    corridor.add_argument("--mode", choices=["auto", "corridor", "pilot"], default="auto")
    corridor.add_argument("--online", action="store_true", help="Download the corridor grid from NASA POWER and USDA CDL")
    corridor.add_argument("--offline", action="store_true", help="Local cache only")
    econ = commands.add_parser("economics", help="Component C inputs: NASS yield/price cache and list of missing inputs")
    econ.add_argument("--config", type=Path, default=root / "config/economics.json")
    econ.add_argument("--inputs", type=Path, default=root / "config/economics_inputs.csv")
    econ.add_argument("--online", action="store_true", help="Download from NASS Quick Stats (needs FIELDSHIFT_NASS_KEY)")
    econ.add_argument("--offline", action="store_true")
    democmd = commands.add_parser("demo", help="One-command usage demo: runs goal, dashboard and app offline and prints a farmer-level summary")
    democmd.add_argument("--open", action="store_true", help="Open the interactive app in the default browser")
    ymodel = commands.add_parser("yield-model", help="Components C/D: NASS county yield ~ climate model and 2040s yield multipliers")
    ymodel.add_argument("--online", action="store_true", help="Download NASS county yields (needs FIELDSHIFT_NASS_KEY)")
    ymodel.add_argument("--offline", action="store_true")
    sat = commands.add_parser("satellite", help="Satellite indicator: MODIS NDVI curve, bare-soil days and CDL phenology check per parcel")
    sat.add_argument("--year", type=int, default=2023)
    sat.add_argument("--max-points", type=int, default=None, help="At most this many parcels (for testing)")
    sat.add_argument("--only", choices=["pilot", "corridor", "all"], default="all")
    sat.add_argument("--online", action="store_true", help="Download from the ORNL DAAC MODIS service (no key needed)")
    sat.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "catalog":
            print(json.dumps(SOURCES, ensure_ascii=False, indent=2))
        elif args.command in ("fetch", "verify"):
            for key in selection(args.dataset):
                result = fetch(args.workspace, key) if args.command == "fetch" else validate_cache(args.workspace, key)
                print(f"{key}: version {result['version']}; {len(result['files'])} files verified.")
        elif args.command in ("run", "analyze"):
            output, metrics = run(args.workspace, args.dataset) if args.command == "run" else run(
                args.workspace, with_analysis=True, pilot=args.pilot, pilot_config=args.config)
            print(json.dumps(metrics, ensure_ascii=False, indent=2))
            print(f"Report: {output / 'REPORT.md'}")
            print(f"Database: {output / 'fieldshift_data.sqlite3'}")
            if args.command == "analyze":
                print(f"Pilot report: {output / 'PILOT_REPORT.md'}")
        elif args.command == "plan":
            output, result = planning.run(args.workspace, args.config)
            print(f"Status: {result['status']}; feasible scenarios: {result['feasible_scenarios']}")
            if result["best"]:
                print(" → ".join(row["crop"] for row in result["best"][0]["schedule"]))
            if args.date:
                print("The date filter works at plan-year level; no day/month planting time was computed.")
                print(json.dumps(planning.at_date(result, args.date), ensure_ascii=False, indent=2))
            print(f"Plan: {output / 'PLAN_REPORT.md'}")
        elif args.command == "plan-view":
            result = json.loads(args.report.read_text(encoding="utf-8"))
            print("The date filter works at plan-year level; no day/month planting time was computed.")
            print(json.dumps(planning.at_date(result, args.date), ensure_ascii=False, indent=2))
        elif args.command == "climate":
            output, result = climate.run(args.workspace, args.site, args.start, args.end, args.kind, args.scenario, args.online)
            print(json.dumps(result["period_summary"], ensure_ascii=False, indent=2))
            print(f"Climate report: {output / 'CLIMATE_REPORT.md'}")
        elif args.command == "seasons":
            if args.online and args.offline:
                raise ValueError("--online and --offline cannot be used together.")
            output, result = alignment.run(args.workspace, args.pilot, args.online)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print(f"Season report: {output / 'SEASON_REPORT.md'}")
        elif args.command == "regional":
            if args.online and args.offline:
                raise ValueError("--online and --offline cannot be used together.")
            output, result = regional.run(args.workspace, args.config, args.online)
            print(f"Sites compared: {len(result['sites'])}; scenario: {result['config']['scenario']}")
            print(f"Regional report: {output / 'REGIONAL_REPORT.md'}")
        elif args.command == "cropland":
            if args.online and args.offline:
                raise ValueError("--online and --offline cannot be used together.")
            output, result = cropland.run(args.workspace, args.config, args.regional_config, args.online)
            print(f"Point-years: {result['observations']}; classifications with wheat: {result['wheat_observations']}")
            print(f"Crop distribution report: {output / 'CROPLAND_REPORT.md'}")
        elif args.command == "goal":
            if args.online and args.offline:
                raise ValueError("--online and --offline cannot be used together.")
            output, result = goal.run(args.workspace, args.economics_config, args.inputs, args.calendar,
                                      args.corridor_config, args.online)
            for key, item in result["status"].items():
                print(f"{key}. {result['components'][key]}: {item['status']} — {item['produced']}")
            if args.date:
                rows = goal.at_date(output, args.date)
                counts = {}
                for row in rows:
                    counts[row["state_on_date"]] = counts.get(row["state_on_date"], 0) + 1
                print(f"Parcel status on {args.date.isoformat()}: " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
                print(json.dumps(rows[:12], ensure_ascii=False, indent=2))
                if len(rows) > 12:
                    print(f"... {len(rows)} rows in total; all of them: goal-view {output.name} --date {args.date.isoformat()}")
            print(f"Goal report: {output / 'GOAL_REPORT.md'}")
            page, _ = dashboard.build(output, args.workspace, args.calendar)
            print(f"Goal dashboard (open in a browser): {page}")
        elif args.command == "dashboard":
            target = args.output
            if target is None:
                runs = sorted((args.workspace / "outputs").glob("goal_*"))
                if not runs:
                    raise ValueError("Run the goal command first.")
                target = runs[-1]
            page, _ = dashboard.build(target, args.workspace, args.calendar)
            print(f"Goal dashboard (open in a browser): {page}")
        elif args.command == "app":
            target = args.output
            if target is None:
                runs = sorted((args.workspace / "outputs").glob("goal_*"))
                if runs:
                    target = runs[-1]
                else:
                    print("No goal output yet; running goal first...")
                    target, _ = goal.run(args.workspace, args.economics_config, args.inputs, args.calendar, args.corridor_config, False)
                    dashboard.build(target, args.workspace, args.calendar)
            if not (Path(target) / "dashboard_data").is_dir():
                dashboard.build(target, args.workspace, args.calendar)
            page, data = app.build(args.workspace, target, args.economics_config, args.inputs, args.calendar)
            print(f"Source goal output: {Path(target).name}; parcels: {len(data['parcels'])}; corridor cells: {len(data['cells'])}")
            print(f"Interface (open in a browser): {page}")
            if args.open:
                import webbrowser
                webbrowser.open(page.resolve().as_uri())
        elif args.command == "goal-view":
            rows = goal.at_date(args.output, args.date)
            if args.parcel:
                rows = [r for r in rows if r["parcel_id"] == args.parcel]
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        elif args.command == "corridor":
            if args.online and args.offline:
                raise ValueError("--online and --offline cannot be used together.")
            output, result = suitability.run(args.workspace, args.config, args.online, args.mode)
            print(f"Source: {result['source']}; trained: {result['readiness']['trained']}")
            for reason in result["readiness"]["reasons"]:
                print(f"- {reason}")
            if result["shift"]:
                print(f"Shift: {result['shift']['distance_km']:.1f} km, {result['shift']['bearing_deg']:.0f}°")
            print(f"Corridor report: {output / 'CORRIDOR_REPORT.md'}")
        elif args.command == "economics":
            if args.online and args.offline:
                raise ValueError("--online and --offline cannot be used together.")
            config = json.loads(args.config.read_text(encoding="utf-8"))
            economics.validate_config(config)
            nass, provenance, problems = economics.nass_inputs(args.workspace, config, args.online)
            merged = economics.merge_inputs(nass, economics.load_inputs(args.inputs))
            for (region, crop), entry in sorted(merged.items()):
                missing = [f for f in ("yield", "price", "cost") if entry.get(f) is None]
                print(f"{region} / {crop}: yield={entry.get('yield')}, price={entry.get('price')}, cost={entry.get('cost')}"
                      + (f"  MISSING: {', '.join(missing)}" if missing else ""))
            for problem in problems[:10]:
                print(f"- {problem}")
            print(f"NASS cache records: {len(provenance)}")
        elif args.command == "demo":
            output, page, lines = demo.run(args.workspace, root / "config/economics.json", root / "config/economics_inputs.csv",
                                           root / "config/crop_calendar.json", root / "config/corridor.json")
            print("\n".join(lines))
            print(f"Demo summary: {output / 'DEMO.md'}")
            if args.open:
                import webbrowser
                webbrowser.open(page.resolve().as_uri())
        elif args.command == "yield-model":
            if args.online and args.offline:
                raise ValueError("--online and --offline cannot be used together.")
            output, report = yieldmodel.run(args.workspace, args.online)
            for crop, m in report["models"].items():
                cv = m.get("cv")
                print(f"{crop}: {m['status']}, {m['cells']} cells" + (f", spatial CV R²={cv['r2']:.2f}" if cv else f" — {m.get('reason', '')}"))
            for problem in report["problems"][:8]:
                print(f"- {problem}")
            print(f"Yield report: {output / 'YIELD_REPORT.md'}  (goal uses these multipliers on its next run)")
        elif args.command == "satellite":
            if args.online and args.offline:
                raise ValueError("--online and --offline cannot be used together.")
            kinds = ("pilot", "corridor") if args.only == "all" else (args.only,)
            output, report = satellite.run(args.workspace, args.year, args.online, args.max_points, kinds)
            agreement = report["phenology_agreement"]
            print(f"NDVI curves for {report['curves']} parcels; CDL–satellite phenology agreement: "
                  + ("—" if agreement is None else f"%{100 * agreement:.0f}"))
            print(f"Satellite report: {output / 'SATELLITE_REPORT.md'}  (app shows it on the parcel card on its next run)")
        elif args.command == "self-test":
            output, result = diagnostics.run(args.workspace, args.online)
            print(f"Test result: {result['status']}; report: {output / 'SELF_TEST.md'}")
            return 0 if result["status"] == "passed" else 1
        elif args.command == "query":
            if not args.database.is_file():
                raise ValueError("Database file not found.")
            uri = args.database.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True) as db:
                db.row_factory = sqlite3.Row
                rows = db.execute("SELECT * FROM pflux_system_comparison WHERE system_id = ?", (args.system,)).fetchall()
            print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))
            if not rows:
                print("No results for this system id.")
    except (OSError, ValueError, KeyError, sqlite3.Error, zipfile.BadZipFile) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
