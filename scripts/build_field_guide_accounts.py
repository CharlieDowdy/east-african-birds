"""Build safe, transparent field-guide account data from the project's existing datasets.

This script deliberately does not invent voice, habitat, behaviour or identification text.
Those fields remain null until supplied from an authoritative source. It does, however,
normalise taxonomy, conservation status, country distribution, photo categories and
source URLs so the web app can present a consistent field-guide account for every taxon.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "field_guide_accounts.json"

COUNTRIES = {
    "Kenya": "KE", "Tanzania": "TZ", "Uganda": "UG", "Rwanda": "RW", "Burundi": "BI",
}


def load(name, default):
    p = DATA / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def status(value):
    s = str(value or "").upper()
    for code, words in {
        "CR": ("CRITICALLY_ENDANGERED", "CR"),
        "EN": ("ENDANGERED", "EN"),
        "VU": ("VULNERABLE", "VU"),
        "NT": ("NEAR_THREATENED", "NT"),
        "LC": ("LEAST_CONCERN", "LC"),
    }.items():
        if any(w in s for w in words):
            return code
    return None


def countries(values):
    found = set()
    for value in values:
        text = str(value or "").upper()
        for name, code in COUNTRIES.items():
            if name.upper() in text or f" {code} " in f" {text} ":
                found.add(code)
    return sorted(found)


def photos_for(photo_record):
    if isinstance(photo_record, list):
        return photo_record
    if not isinstance(photo_record, dict):
        return []
    result = []
    for category, items in photo_record.items():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    result.append({"category": category, **item})
    return result


def main():
    species = load("species.json", {}).get("species", [])
    details = load("species_details.json", {}).get("species", {})
    photos = load("photos.json", {}).get("species", {})

    accounts = {}
    for bird in species:
        bird_id = bird.get("id")
        if not bird_id:
            continue
        detail = details.get(bird_id, {})
        raw_distribution = detail.get("distribution", [])
        if not isinstance(raw_distribution, list):
            raw_distribution = [raw_distribution]
        distribution = countries([
            bird.get("range"), bird.get("country"), bird.get("countries"),
            detail.get("country"), detail.get("countries"), raw_distribution,
        ])
        accounts[bird_id] = {
            "id": bird_id,
            "name": bird.get("name"),
            "scientific_name": bird.get("scientific") or detail.get("matched_name"),
            "order": bird.get("order"),
            "family": bird.get("family"),
            "genus": bird.get("genus"),
            "conservation_status": status(bird.get("status") or detail.get("conservation_status")),
            "east_africa": {
                "countries": distribution,
                "range_text": bird.get("range"),
            },
            "identification": None,
            "similar_species": [],
            "voice": None,
            "habitat": None,
            "behaviour": None,
            "seasonal_movements": None,
            "plumages": [],
            "photos": photos_for(photos.get(bird_id, {})),
            "sources": detail.get("sources", []),
            "data_status": {
                "account": "generated_from_project_data",
                "missing_prose": [
                    "identification", "similar_species", "voice", "habitat",
                    "behaviour", "seasonal_movements",
                ],
            },
        }

    OUT.write_text(json.dumps({
        "version": 1,
        "scope": ["KE", "TZ", "UG", "RW", "BI"],
        "generated_by": "scripts/build_field_guide_accounts.py",
        "notes": "Null prose fields are intentional: the generator never invents natural-history facts.",
        "species": accounts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(accounts)} field-guide accounts to {OUT}")


if __name__ == "__main__":
    main()
