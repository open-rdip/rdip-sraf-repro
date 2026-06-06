"""
Parses machine-actionable DMP (maDMP) JSON files conforming
to the RDA DMP Common Standard into a normalised dict
ready for RDIP mapping.

Input: JSON file following https://doi.org/10.15497/rda00039
Output: dict with keys: project, datasets, licenses,
        access_levels, repositories, contributors
"""

import json
from pathlib import Path


def parse_madmp(dmp_path: str) -> dict:
    """Parse an maDMP JSON file into normalised structure."""
    raw = json.loads(Path(dmp_path).read_text())

    # RDA DMP Common Standard nests everything under "dmp"
    dmp = raw.get("dmp", raw)

    result = {
        "dmp_id": dmp.get("dmp_id", {}).get("identifier", ""),
        "title": dmp.get("title", ""),
        "created": dmp.get("created", ""),
        "modified": dmp.get("modified", ""),
        "project": _extract_project(dmp),
        "datasets": _extract_datasets(dmp),
        "contributors": _extract_contributors(dmp),
        "costs": _extract_costs(dmp),
    }
    return result


def _extract_project(dmp: dict) -> dict:
    projects = dmp.get("project", [])
    if not projects:
        return {}
    p = projects[0]
    funding = p.get("funding", [{}])[0] if p.get("funding") else {}
    return {
        "title": p.get("title", ""),
        "start": p.get("start", ""),
        "end": p.get("end", ""),
        "funder_name": funding.get("funder_id", {}).get("identifier", ""),
        "grant_id": funding.get("grant_id", {}).get("identifier", ""),
    }


def _extract_datasets(dmp: dict) -> list:
    datasets = []
    for ds in dmp.get("dataset", []):
        distributions = []
        for dist in ds.get("distribution", []):
            distributions.append({
                "title": dist.get("title", ""),
                "access_url": dist.get("access_url", ""),
                "data_access": dist.get("data_access", ""),  # open/shared/closed
                "host": dist.get("host", {}).get("title", ""),
                "license": (dist.get("license", [{}])[0].get("license_ref", "")
                           if dist.get("license") else ""),
            })
        datasets.append({
            "title": ds.get("title", ""),
            "dataset_id": ds.get("dataset_id", {}).get("identifier", ""),
            "type": ds.get("type", ""),
            "personal_data": ds.get("personal_data", "unknown"),
            "sensitive_data": ds.get("sensitive_data", "unknown"),
            "distributions": distributions,
        })
    return datasets


def _extract_contributors(dmp: dict) -> list:
    return [
        {
            "name": c.get("name", ""),
            "orcid": c.get("contributor_id", {}).get("identifier", ""),
            "role": c.get("role", []),
        }
        for c in dmp.get("contributor", [])
    ]


def _extract_costs(dmp: dict) -> list:
    return [
        {
            "title": c.get("title", ""),
            "value": c.get("value", 0),
            "currency": c.get("currency_code", ""),
        }
        for c in dmp.get("cost", [])
    ]
