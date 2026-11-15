"""Pinned public data releases; verified against Figshare API on 2026-11-15."""

SOURCES = {
    "pflux": {
        "article_id": 24855381,
        "version": 1,
        "title": "LTAR Phosphorus Budget Summary",
        "doi": "https://doi.org/10.15482/USDA.ADC/1523365",
        "page": "https://agdatacommons.nal.usda.gov/articles/dataset/LTAR_Phosphorus_Budget_Summary/24855381",
        "files": [
            {"id": 44530277, "name": "DataSourcesAndReferences.csv", "size": 45384,
             "md5": "307469c3ffb076258f4db84d424e9ca4"},
            {"id": 44530280, "name": "PBudgetData.csv", "size": 67501,
             "md5": "ce25c5543acbef3432d781f9ae7a23a1"},
        ],
    },
    "napeshm": {
        "article_id": 25632270,
        "version": 1,
        "title": "North American Project to Evaluate Soil Health Measurements Dataset",
        "doi": "https://doi.org/10.15482/USDA.ADC/25632270",
        "page": "https://agdatacommons.nal.usda.gov/articles/dataset/North_American_Project_to_Evaluate_Soil_Health_Measurements_Dataset/25632270",
        "files": [
            {"id": 46794877, "name": "NAPESHM_public_dataset_06032024.zip", "size": 4994407,
             "md5": "b6a0a7cd8123c556c82a0d3384084a83"},
        ],
    },
}


def source_directory(workspace, key):
    return workspace / "data" / "raw" / key / f"v{SOURCES[key]['version']}"


def selection(dataset):
    return tuple(SOURCES) if dataset == "all" else (dataset,)
