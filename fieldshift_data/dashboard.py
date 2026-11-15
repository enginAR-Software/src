"""Goal dashboard: a single-file, offline DASHBOARD.html and dashboard data tables built from a goal output.

All numbers come from the goal/corridor outputs or the packaged NASA daily projection.
"""

from collections import Counter, defaultdict
import csv
from datetime import date
import html
import json
from pathlib import Path
from statistics import median

from . import planting
from .tables import write_csv

PERIODS = {"2016–2024": range(2016, 2025), "2041–2049": range(2041, 2050)}
STATUS_LABELS = {"working": "Working", "awaiting_inputs": "Awaiting inputs", "awaiting_data": "Awaiting data",
             "trained": "Trained", "insufficient_training_data": "Insufficient training data"}
STRATEGY_LABELS = {"current": "Current rotation", "most_profitable": "Most profitable", "wheat_focused": "Wheat-focused"}
CROP_LABELS = {"Winter Wheat": "Winter wheat", "Spring Wheat": "Spring wheat", "Corn": "Corn", "Soybeans": "Soybeans",
           "Sorghum": "Sorghum", "Peas": "Peas", "Fallow/Idle Cropland": "Fallow", "Alfalfa": "Alfalfa",
           "Other Hay/Non Alfalfa": "Hay", "Triticale": "Triticale", "Dbl Crop WinWht/Soybeans": "Wheat+soy (double)"}
REGION_TR = {"USKS01": "Kansas (USKS01)", "USOR03": "Oregon (USOR03)"}


def read_csv(path):
    with Path(path).open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def doy(iso):
    d = date.fromisoformat(iso)
    return (d - date(d.year, 1, 1)).days + 1


def doy_label(value):
    d = date(2023, 1, 1).toordinal() + int(round(value)) - 1
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    dd = date.fromordinal(d)
    return f"{dd.day} {months[dd.month - 1]}"


def window_shift(workspace, regions, crops_by_region, calendar_path):
    """Median planting window per region × crop from the actual daily projection of 2016–2024 and 2041–2049."""
    calendar = planting.load_calendar(calendar_path)
    rows = []
    for region in regions:
        daily, _ = planting.load_site_daily(workspace, region)
        for crop in crops_by_region[region]:
            rule = calendar["crops"].get(crop)
            if not rule or rule["type"] == "none":
                continue
            for label, years in PERIODS.items():
                starts, ends, used, normal = [], [], 0, 0
                cache = {}
                for year in years:
                    result = planting.window(daily, crop, year, calendar, cache)
                    if result["status"] in ("ok", "start_only", "low_confidence") and result["start"]:
                        used += 1
                        normal += "normal " in (result["basis"] or "")
                        offset = 365 if rule["type"] == "winter" else 0
                        starts.append(doy(result["start"]) - offset)
                        if result["end"]:
                            ends.append(doy(result["end"]) - offset)
                rows.append({"region": region, "crop": crop, "period": label, "years_used": used,
                             "years_from_period_normal": normal,
                             "median_start_doy": median(starts) if starts else None,
                             "median_end_doy": median(ends) if ends else None,
                             "season": "autumn (previous year)" if rule["type"] == "winter" else "spring"})
    return rows


def build(goal_dir, workspace, calendar_path):
    goal_dir = Path(goal_dir)
    report = json.loads((goal_dir / "goal.json").read_text(encoding="utf-8"))
    strategies = read_csv(goal_dir / "parcel_strategies.csv")
    plans = read_csv(goal_dir / "parcel_plans.csv")
    parcels = json.loads((goal_dir / "parcels.geojson").read_text(encoding="utf-8"))["features"]
    corridor_dir = Path(workspace) / "outputs" / report["corridor_output"]
    cells = read_csv(corridor_dir / "corridor_cells.csv") if (corridor_dir / "corridor_cells.csv").is_file() else []

    components = [{"key": k, "component": report["components"][k], "status": report["status"][k]["status"],
                   "status_label": STATUS_LABELS.get(report["status"][k]["status"], report["status"][k]["status"]),
                   "produced": report["status"][k]["produced"], "next": report["status"][k]["next"]} for k in "ABCDE"]

    summary = []
    groups = defaultdict(list)
    for row in strategies:
        groups[(row["region"], row["strategy"])].append(row)
    for (region, strategy), rows in sorted(groups.items()):
        profits = [float(r["total_profit_usd_per_acre"]) for r in rows if r["total_profit_usd_per_acre"]]
        p_rem = [float(r["cumulative_p_removal_kg_per_ha"]) for r in rows if r["cumulative_p_removal_kg_per_ha"]]
        modal = Counter(r["sequence"] for r in rows if r["sequence"]).most_common(1)
        summary.append({"region": region, "strategy": strategy, "strategy_tr": STRATEGY_LABELS.get(strategy, strategy),
                        "parcels": len(rows), "parcels_with_profit": len(profits),
                        "mean_profit_usd_per_acre": round(sum(profits) / len(profits), 1) if profits else None,
                        "min_profit": round(min(profits), 1) if profits else None,
                        "max_profit": round(max(profits), 1) if profits else None,
                        "mean_p_removal_kg_per_ha": round(sum(p_rem) / len(p_rem), 1) if p_rem else None,
                        "typical_sequence": modal[0][0] if modal else None})

    parcel_rows = []
    best_first = {}
    for row in plans:
        if row["strategy"] == "most_profitable" and row["plan_year"] == str(report["plan_years"][0]):
            best_first[row["parcel_id"]] = row
    for feature in parcels:
        p = feature["properties"]
        first = best_first.get(p["parcel_id"], {})
        parcel_rows.append({"parcel_id": p["parcel_id"], "region": p["region"],
                            "longitude": feature["geometry"]["coordinates"][0], "latitude": feature["geometry"]["coordinates"][1],
                            "observed_sequence": p["observed_sequence"], "current_rotation": p["current_rotation"],
                            "best_rotation": p["best_rotation"], "first_crop": first.get("crop"),
                            "first_planting_start": first.get("planting_start") or None,
                            "first_planting_end": first.get("planting_end") or None})

    yearly = [{"parcel_id": r["parcel_id"], "region": r["region"], "strategy": r["strategy"], "plan_year": r["plan_year"],
               "crop": r["crop"], "crop_tr": CROP_LABELS.get(r["crop"], r["crop"]), "planting_start": r["planting_start"] or None,
               "planting_end": r["planting_end"] or None, "profit_usd_per_acre": r["expected_profit_usd_per_acre"] or None}
              for r in plans if r["strategy"] == "most_profitable"]

    regions = sorted({r["region"] for r in parcel_rows})
    crops_by_region = defaultdict(set)
    for r in plans:
        crops_by_region[r["region"]].add(r["crop"])
    shift = window_shift(workspace, regions, crops_by_region, calendar_path)

    climate = []
    labels = {"t_mean_c": "Annual mean temp. (°C)", "gdd0_annual": "GDD, base 0°C", "tmax_jun_jul_c": "Jun–Jul mean Tmax (°C)",
              "prec_annual_mm": "Annual precipitation (mm)", "prec_oct_jun_mm": "Oct–Jun precipitation (mm)"}
    for c in cells:
        for key, label in labels.items():
            b, f = c.get(f"baseline_{key}"), c.get(f"future_{key}")
            if b and f:
                climate.append({"cell_id": c["cell_id"], "metric": label, "baseline_2015_2024": round(float(b), 2),
                                "future_2040_2049": round(float(f), 2), "change": round(float(f) - float(b), 2)})

    out = goal_dir / "dashboard_data"
    write_csv(out / "components.csv", components)
    write_csv(out / "strategy_summary.csv", summary)
    write_csv(out / "parcels.csv", parcel_rows)
    write_csv(out / "best_plan_years.csv", yearly)
    write_csv(out / "planting_shift.csv", shift)
    write_csv(out / "climate_shift.csv", climate)
    if cells and any(c.get("suitability_baseline") for c in cells):
        write_csv(out / "corridor_cells.csv", cells)
    data = {"components": components, "summary": summary, "parcels": parcel_rows, "plan": yearly, "shift": shift, "climate": climate,
            "cells": cells, "corridor": report["corridor"], "goal": report["goal"], "plan_years": report["plan_years"],
            "p_removal": report["economics"]["p_removal_kg_per_ha"]}
    (goal_dir / "DASHBOARD.html").write_text(render(data), encoding="utf-8")
    return goal_dir / "DASHBOARD.html", data


def render(data):
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", payload).replace("__GOAL__", html.escape(data["goal"]))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FieldShift goal dashboard</title>
<style>
:root{--bg:#f7f6f2;--card:#fff;--ink:#1f2328;--muted:#5f6670;--line:#e3e1da;--ok:#2f7d4f;--wait:#b7791f;--no:#a33a3a;
--c1:#3b6fb6;--c2:#d0802c;--c3:#5a9a6b;--c4:#8d5fb0;--c5:#c25d7a;--c6:#6b7a8c}
@media (prefers-color-scheme:dark){:root{--bg:#16181b;--card:#1f2226;--ink:#e8e6e1;--muted:#a0a6ad;--line:#33373c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:28px 18px 60px}h1{font-size:26px;margin:0 0 6px}h2{font-size:19px;margin:34px 0 10px}
.lead{color:var(--muted);max-width:820px}.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.badge{display:inline-block;font-size:12px;font-weight:600;padding:2px 8px;border-radius:99px;color:#fff}
.k{font-size:28px;font-weight:700;margin-right:6px}.small{font-size:13px;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{font-weight:600;color:var(--muted)}td.num{text-align:right;font-variant-numeric:tabular-nums}
svg text{fill:var(--ink);font-size:12px}.axis line,.axis path{stroke:var(--line)}.tip{white-space:pre-line;position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);padding:6px 8px;border-radius:6px;font-size:12px;display:none;max-width:280px}
.scroll{overflow-x:auto}.chips span{display:inline-block;margin:2px 6px 2px 0;font-size:12px}.chips i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
</style></head><body><main>
<h1>FieldShift goal dashboard</h1>
<p class="lead">__GOAL__</p>
<div class="grid" id="components"></div>
<h2 id="h-calendar">E. When to plant each year — and how the calendar shifts as the climate changes</h2>
<p class="small">Planting windows from the NASA NEX-GDDP (SSP2-4.5) daily projection with sourced thresholds: median of 2016–2024 and 2041–2049. Winter wheat is sown in the previous autumn.</p>
<div id="calendar"></div>
<h2 id="h-strategy">C. Economically most efficient rotation per parcel</h2>
<p class="small">Mean total economic profit over the plan years (USD/acre). The cost of replacing removed phosphorus is deducted.</p>
<div id="strategy"></div><div id="strategy-table"></div>
<h2 id="h-parcels">B + E. What to plant on each parcel every year</h2>
<div id="parcels"></div>
<h2 id="h-corridor">A + D. The region wheat will migrate to</h2>
<div id="corridor"></div>
<p class="small" style="margin-top:30px">This dashboard supports decisions; it does not replace the judgement of the farmer or a local expert. Sources and method: docs/METHODS.md.</p>
</main><div class="tip" id="tip"></div>
<script>
const D=__DATA__;
const COL={ "Working":"var(--ok)","Trained":"var(--ok)","Awaiting inputs":"var(--wait)","Awaiting data":"var(--wait)","Insufficient training data":"var(--no)"};
const CROP={"Winter Wheat":"Winter wheat","Spring Wheat":"Spring wheat","Corn":"Corn","Soybeans":"Soybeans","Sorghum":"Sorghum","Peas":"Peas","Fallow/Idle Cropland":"Fallow","Alfalfa":"Alfalfa","Other Hay/Non Alfalfa":"Hay","Triticale":"Triticale","Dbl Crop WinWht/Soybeans":"Wheat+soy"};
const CC={"Winter Wheat":"var(--c2)","Spring Wheat":"var(--c5)","Corn":"var(--c1)","Soybeans":"var(--c3)","Sorghum":"var(--c4)","Peas":"var(--c6)","Fallow/Idle Cropland":"#b9b3a6"};
const REG={"USKS01":"Kansas","USOR03":"Oregon"};
const NS="http://www.w3.org/2000/svg";const tip=document.getElementById("tip");
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
function h(t,txt,p){const e=document.createElement(t);if(txt!=null)e.textContent=txt;if(p)p.appendChild(e);return e}
function showTip(ev,txt){tip.textContent=txt;tip.style.display="block";tip.style.left=Math.min(ev.clientX+12,innerWidth-290)+"px";tip.style.top=(ev.clientY+12)+"px"}
function hideTip(){tip.style.display="none"}
function months(){return["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]}
function dlabel(v){const d=new Date(2023,0,1);d.setDate(d.getDate()+Math.round(v)-1);return d.getDate()+" "+months()[d.getMonth()]}
// Components
const comp=document.getElementById("components");
D.components.forEach(c=>{const card=h("div",null,comp);card.className="card";const t=h("div",null,card);const k=h("span",c.key,t);k.className="k";
const b=h("span",c.status_label,t);b.className="badge";b.style.background=COL[c.status_label]||"var(--muted)";
h("div",c.component,card).style.fontWeight="600";const p=h("div",c.produced,card);p.className="small"});
// Calendar
function drawCalendar(){const box=document.getElementById("calendar");box.innerHTML="";
const rows=D.shift.filter(r=>r.median_start_doy!==null);const W=box.clientWidth||900,L=Math.min(210,W*0.42),R=16,rowH=34;
const groups=[...new Set(rows.map(r=>r.region+"|"+r.crop))];const H=groups.length*rowH+40;
const svg=el("svg",{width:W,height:H},box);const x0=-120,x1=245;const sx=v=>L+(v-x0)/(x1-x0)*(W-L-R);
[-92,-61,-31,1,32,60,91,121,152,182,213,244].forEach((d,i)=>{if(W<640&&i%2)return;const lab=["Oct","Nov","Dec","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep"][i];
el("line",{x1:sx(d),x2:sx(d),y1:20,y2:H-6,stroke:"var(--line)"},svg);const t=el("text",{x:sx(d)+3,y:14},svg);t.textContent=lab});
groups.forEach((g,i)=>{const [reg,crop]=g.split("|");const y=26+i*rowH;const t=el("text",{x:4,y:y+16},svg);t.textContent=REG[reg]+" · "+(CROP[crop]||crop);if(W<640)t.setAttribute("font-size","11");
["2016–2024","2041–2049"].forEach((per,j)=>{const r=rows.find(q=>q.region===reg&&q.crop===crop&&q.period===per);if(!r)return;
const s=r.median_start_doy,e=r.median_end_doy;const yy=y+4+j*12;const col=j?"var(--no)":"var(--c1)";
if(e!==null&&e>s){const rect=el("rect",{x:sx(s),y:yy,width:Math.max(3,sx(e)-sx(s)),height:9,rx:2,fill:col,opacity:j?0.85:0.65},svg);
rect.addEventListener("mousemove",ev=>showTip(ev,`${REG[reg]} · ${CROP[crop]||crop} · ${per}: ${dlabel(s<1?s+365:s)} – ${dlabel(e<1?e+365:e)} (${r.years_used} years)`));rect.addEventListener("mouseleave",hideTip)}
else{const c=el("circle",{cx:sx(s),cy:yy+4.5,r:4,fill:col},svg);c.addEventListener("mousemove",ev=>showTip(ev,`${REG[reg]} · ${CROP[crop]||crop} · ${per}: earliest ${dlabel(s<1?s+365:s)} (no end rule)`));c.addEventListener("mouseleave",hideTip)}})});
const lg=h("div",null,box);lg.className="chips";lg.innerHTML='<span><i style="background:var(--c1)"></i>2016–2024</span><span><i style="background:var(--no)"></i>2041–2049</span>'}
// Strategies
function drawStrategy(){const box=document.getElementById("strategy");box.innerHTML="";const rows=D.summary.filter(r=>r.mean_profit_usd_per_acre!==null&&r.mean_profit_usd_per_acre!=="");
const regs=[...new Set(rows.map(r=>r.region))];const order=["current","wheat_focused","most_profitable"];const W=box.clientWidth||900,L=170,R=60,bh=22;
const H=regs.length*(order.length*bh+26)+20;const vals=rows.map(r=>+r.mean_profit_usd_per_acre);const mn=Math.min(0,...vals),mx=Math.max(0,...vals);
const svg=el("svg",{width:W,height:H},box);const sx=v=>L+(v-mn)/(mx-mn||1)*(W-L-R);let y=10;
regs.forEach(reg=>{const t=el("text",{x:4,y:y+12},svg);t.textContent=REG[reg];t.setAttribute("font-weight","600");y+=18;
order.forEach(st=>{const r=rows.find(q=>q.region===reg&&q.strategy===st);if(!r){y+=bh;return}const v=+r.mean_profit_usd_per_acre;
const lab=el("text",{x:14,y:y+14},svg);lab.textContent=r.strategy_tr;const col=st==="most_profitable"?"var(--ok)":st==="current"?"var(--c6)":"var(--c2)";
const rect=el("rect",{x:Math.min(sx(0),sx(v)),y:y+2,width:Math.max(2,Math.abs(sx(v)-sx(0))),height:bh-6,rx:3,fill:col},svg);
rect.addEventListener("mousemove",ev=>showTip(ev,`${r.strategy_tr}: ${r.typical_sequence.split(" → ").map(c=>CROP[c]||c).join(" → ")}`));rect.addEventListener("mouseleave",hideTip);
const vt=el("text",{x:v>=0?sx(v)+4:sx(v)-4,y:y+14,"text-anchor":v>=0?"start":"end"},svg);vt.textContent=(v>=0?"+":"")+v.toFixed(0)+" $";y+=bh});y+=8});
el("line",{x1:sx(0),x2:sx(0),y1:4,y2:H-4,stroke:"var(--muted)"},svg);
const tb=document.getElementById("strategy-table");tb.innerHTML="";const sc0=h("div",null,tb);sc0.className="scroll";const table=h("table",null,sc0);const hd=h("tr",null,h("thead",null,table));
["Region","Strategy","Typical sequence (6 years)","Mean profit $/acre","Mean P removal kg/ha"].forEach(x=>h("th",x,hd));const bd=h("tbody",null,table);
D.summary.forEach(r=>{const tr=h("tr",null,bd);h("td",REG[r.region],tr);h("td",r.strategy_tr,tr);h("td",r.typical_sequence?r.typical_sequence.split(" → ").map(c=>CROP[c]||c).join(" → "):"girdi bekleniyor",tr);
const a=h("td",r.mean_profit_usd_per_acre===null||r.mean_profit_usd_per_acre===""?"—":(+r.mean_profit_usd_per_acre).toFixed(0),tr);a.className="num";const b=h("td",r.mean_p_removal_kg_per_ha===null||r.mean_p_removal_kg_per_ha===""?"—":(+r.mean_p_removal_kg_per_ha).toFixed(0),tr);b.className="num"})}
// Parcels: year × parcel rotation table (most profitable plan)
function drawParcels(){const box=document.getElementById("parcels");box.innerHTML="";
const regs=[...new Set(D.parcels.map(p=>p.region))];
regs.forEach(reg=>{const card=h("div",null,box);card.className="card";card.style.marginBottom="12px";
h("div",REG[reg]+" — yearly crops of the most profitable plan",card).style.fontWeight="600";
const rows=D.plan.filter(r=>r.region===reg);const groups={};
rows.forEach(r=>{(groups[r.parcel_id]=groups[r.parcel_id]||[]).push(r)});
const seqs={};Object.entries(groups).forEach(([pid,list])=>{list.sort((a,b)=>a.plan_year-b.plan_year);const key=list.map(x=>x.crop).join("|");(seqs[key]=seqs[key]||{list,ids:[]}).ids.push(pid)});
const years=D.plan_years;const sc=h("div",null,card);sc.className="scroll";const table=h("table",null,sc);const hd=h("tr",null,h("thead",null,table));h("th","Parcels",hd);years.forEach(y=>h("th",String(y),hd));
const bd=h("tbody",null,table);
if(!Object.keys(seqs).length){const tr=h("tr",null,bd);const td=h("td","Awaiting economic inputs; the current rotation applies.",tr);td.colSpan=years.length+1}
Object.values(seqs).forEach(g=>{const tr=h("tr",null,bd);h("td",g.ids.length+" parcels",tr).className="small";
g.list.forEach(x=>{const td=h("td",null,tr);const chip=h("div",CROP[x.crop]||x.crop,td);chip.style.cssText=`background:${CC[x.crop]||"var(--muted)"};color:#fff;border-radius:5px;padding:3px 6px;font-size:12px;text-align:center;white-space:nowrap`;
const when=x.planting_start?(x.planting_start+(x.planting_end?" – "+x.planting_end:"")):"no planting";
const sub=h("div",x.planting_start?x.planting_start.slice(5).split("-").reverse().join(".")+(x.planting_end?"–"+x.planting_end.slice(5).split("-").reverse().join("."):""):"",td);sub.className="small";sub.style.textAlign="center";
td.addEventListener("mousemove",ev=>showTip(ev,`${x.plan_year} · ${CROP[x.crop]||x.crop}\nEkim: ${when}\nBeklenen kâr: ${x.profit_usd_per_acre!==null&&x.profit_usd_per_acre!==""?(+x.profit_usd_per_acre).toFixed(0)+" $/acre":"—"}`));td.addEventListener("mouseleave",hideTip)})});
h("div","The date under each cell is the planting window (month-day). Winter wheat is sown in the previous autumn. Crop histories and locations are in parcels.csv / parcels.geojson.",card).className="small"})}
// Corridor
function drawCorridor(){const box=document.getElementById("corridor");box.innerHTML="";const c=D.corridor;
if(c.shift&&D.cells.some(x=>x.suitability_baseline)){const cells=D.cells.filter(x=>x.suitability_baseline);const W=box.clientWidth||900;const half=W<640;
const wrap=h("div",null,box);wrap.className="grid";wrap.style.gridTemplateColumns=half?"1fr":"1fr 1fr";
["suitability_baseline","suitability_future"].forEach((key,j)=>{const card=h("div",null,wrap);card.className="card";h("div",j?"2040–2049 suitability":"2015–2024 suitability",card).style.fontWeight="600";
const w=Math.max(260,card.clientWidth-28);const lons=cells.map(x=>+x.longitude),lats=cells.map(x=>+x.latitude);const x0=Math.min(...lons)-0.5,x1=Math.max(...lons)+0.5,y0=Math.min(...lats)-0.5,y1=Math.max(...lats)+0.5;
const H=w*(y1-y0)/(x1-x0);const svg=el("svg",{width:w,height:H},card);const sx=v=>(v-x0)/(x1-x0)*w,sy=v=>H-(v-y0)/(y1-y0)*H;const cw=sx(1)-sx(0);
cells.forEach(x=>{const v=+x[key];const r=el("rect",{x:sx(+x.longitude-0.5),y:sy(+x.latitude+0.5),width:cw-1,height:cw-1,fill:`rgba(208,128,44,${0.08+0.9*v})`},svg);
r.addEventListener("mousemove",ev=>showTip(ev,`${x.cell_id}: uygunluk ${v.toFixed(2)}`));r.addEventListener("mouseleave",hideTip)});
const ctr=j?c.shift.future_centroid:c.shift.baseline_centroid;el("circle",{cx:sx(ctr.longitude),cy:sy(ctr.latitude),r:6,fill:"none",stroke:"var(--ink)","stroke-width":2},svg)});
const z=c.shift.suitable_zone;const p=h("p",null,box);p.textContent=z?`Suitable zone (probability ≥ ${z.threshold}) grows from ${z.cells_baseline} to ${z.cells_future} cells; its centre moves ${z.distance_km.toFixed(0)} km at ${z.bearing_deg.toFixed(0)}°. Gained ${z.cells_gained}, lost ${z.cells_lost} cells.`:`The suitability centre moves ${c.shift.distance_km.toFixed(0)} km.`;
if(c.validation){const v=h("p",`Model validation (spatial block): AUC ${c.validation.auc?c.validation.auc.toFixed(3):"—"}`,box);v.className="small"}}
else{const card=h("div",null,box);card.className="card";h("div","The migration map needs corridor data",card).style.fontWeight="600";
h("div",(c.readiness.reasons||[]).join(" · "),card).className="small";h("p","Command: python3 -m fieldshift_data corridor --online  →  then rerun goal and dashboard.",card).className="small";
if(D.climate.length){h("div","Climate shift already visible at the pilot sites (same NASA model, 2015–2024 → 2040–2049):",card).style.marginTop="10px";
const table=h("table",null,card);const hd=h("tr",null,h("thead",null,table));["Site","Indicator","2015–2024","2040–2049","Change"].forEach(x=>h("th",x,hd));const bd=h("tbody",null,table);
D.climate.forEach(r=>{const tr=h("tr",null,bd);h("td",REG[r.cell_id]||r.cell_id,tr);h("td",r.metric,tr);[r.baseline_2015_2024,r.future_2040_2049].forEach(v=>{const td=h("td",(+v).toFixed(1),tr);td.className="num"});
const d=h("td",((+r.change)>=0?"+":"")+(+r.change).toFixed(1),tr);d.className="num";d.style.fontWeight="600"})}}}
function all(){drawCalendar();drawStrategy();drawParcels();drawCorridor()}all();let tm;addEventListener("resize",()=>{clearTimeout(tm);tm=setTimeout(all,150)});
</script></body></html>"""
