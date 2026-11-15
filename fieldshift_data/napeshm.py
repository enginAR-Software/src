"""Keep experimental identity, assay methods and site-level wheat flags."""

from collections import Counter, defaultdict
import re
import statistics

from .tables import is_missing, numeric, require, unique_index


INDICATORS = ("b_soc", "b_total_n", "b_ph", "b_p_m3", "b_p_olsen", "b_k_m3", "b_k_amac",
              "b_pmn_am_mgkg", "d_h3a_no3")


def prepare(tables):
    for name in ("sites", "treatments", "soildata", "dbcolumns", "mgmtdata"):
        if name not in tables:
            raise ValueError(f"NAPESHM table missing: {name}")
    sites = unique_index(tables["sites"], "siteid")
    treatments = unique_index(tables["treatments"], "treatmentid")
    unique_index(tables["soildata"], "euid")
    require(tables["sites"], ["sitecode", "site_wheat", "country", "state_prov", "studyname"])
    require(tables["treatments"], ["siteid", "sitecode", "crop_phase", "eu_crop_rot", "eu_tillage", "eu_cover_crops"])
    require(tables["soildata"], ["siteid", "treatmentid", "sitecode"] + list(INDICATORS))
    require(tables["dbcolumns"], ["dbtablename", "dbcolname", "unit", "description", "interpretive_name"])
    for row in treatments.values():
        site = sites.get(row["siteid"])
        if site is None or site["sitecode"] != row["sitecode"]:
            raise ValueError("NAPESHM treatment → site relation does not match.")
    dictionary = {(r["dbtablename"], r["dbcolname"]): r for r in tables["dbcolumns"].rows}
    for indicator in INDICATORS:
        if ("soildata", indicator) not in dictionary:
            raise ValueError(f"Indicator dictionary missing: {indicator}")
    joined, observations = [], []
    groups = defaultdict(list)
    for soil in tables["soildata"].rows:
        site = sites.get(soil["siteid"])
        treatment = treatments.get(soil["treatmentid"])
        if (site is None or treatment is None or treatment["siteid"] != soil["siteid"]
                or soil["sitecode"] != site["sitecode"]):
            raise ValueError(f"NAPESHM soil → treatment/site relation does not match: {soil['euid']}")
        context = {
            "site_country": site["country"], "site_state": site["state_prov"],
            "site_study": site["studyname"], "site_wheat_flag": site["site_wheat"],
            "treatment_crop_phase": treatment["crop_phase"],
            "phase_mentions_wheat": bool(re.search(r"wheat", treatment["crop_phase"], re.I)),
            "treatment_rotation_category": treatment["eu_crop_rot"],
            "treatment_tillage": treatment["eu_tillage"],
            "treatment_cover_crops": treatment["eu_cover_crops"],
        }
        joined.append({**soil, **context})
        for indicator in INDICATORS:
            meta = dictionary[("soildata", indicator)]
            raw = soil[indicator]
            value = numeric(raw)
            observations.append({
                "euid": soil["euid"], "siteid": soil["siteid"], "treatmentid": soil["treatmentid"],
                "sitecode": soil["sitecode"], "indicator": indicator,
                "interpretive_name": meta["interpretive_name"], "value": value,
                "raw_value": raw, "unit": meta["unit"], "method": meta["description"],
                "value_status": "missing" if is_missing(raw) else "numeric" if value is not None else "unparsed",
            })
            if value is not None:
                groups[(soil["siteid"], soil["treatmentid"], indicator)].append(value)
    stats = []
    for (siteid, treatmentid, indicator), values in sorted(groups.items()):
        meta = dictionary[("soildata", indicator)]
        stats.append({"siteid": siteid, "treatmentid": treatmentid, "indicator": indicator,
                      "n_plots": len(values), "mean": statistics.fmean(values),
                      "min": min(values), "max": max(values), "unit": meta["unit"], "method": meta["description"]})
    wheat_sites = [dict(row) for row in sites.values() if row["site_wheat"] == "1"]
    observed_by_site = Counter(row["siteid"] for row in joined)
    observed_treatments = defaultdict(set)
    for row in joined:
        observed_treatments[row["siteid"]].add(row["treatmentid"])
    wheat_coverage = [{"siteid": site["siteid"], "sitecode": site["sitecode"],
                       "studyname": site["studyname"], "soil_plot_count": observed_by_site[site["siteid"]],
                       "observed_treatment_count": len(observed_treatments[site["siteid"]]),
                       "has_soil_data": observed_by_site[site["siteid"]] > 0} for site in wheat_sites]
    # Management events are NOT joined to soil rows: that would multiply observations.
    require(tables["mgmtdata"], ["treatmentid", "sitecode", "category", "date"])
    bad_event_links = 0
    for row in tables["mgmtdata"].rows:
        treatment = treatments.get(row["treatmentid"])
        if treatment is None or treatment["sitecode"] != row["sitecode"]:
            bad_event_links += 1
    info = {"sites": len(sites), "treatments": len(treatments), "soil_plots": len(joined),
            "soil_observed_sites": len(observed_by_site),
            "wheat_flagged_sites": len(wheat_sites),
            "wheat_sites_with_soil": sum(row["has_soil_data"] for row in wheat_coverage),
            "wheat_sites_without_soil": [row["sitecode"] for row in wheat_coverage if not row["has_soil_data"]],
            "wheat_phase_plots": sum(r["phase_mentions_wheat"] for r in joined),
            "wheat_flagged_site_plots": sum(r["site_wheat_flag"] == "1" for r in joined),
            "management_rows": len(tables["mgmtdata"].rows),
            "management_invalid_links": bad_event_links,
            "reserved_management_rows": sum(r["category"].casefold() == "reserved index row" for r in tables["mgmtdata"].rows),
            "unparsed_indicator_values": sum(r["value_status"] == "unparsed" for r in observations),
            "notice": "Cross-sectional soil indicators; site_wheat is site level. Total N is not mineral N. Measurement methods were kept separate."}
    return {"soil_with_context": joined, "soil_indicators": observations,
            "treatment_summary": stats, "wheat_candidate_sites": wheat_sites,
            "wheat_site_coverage": wheat_coverage}, info
