"""Build transparent field-guide account data from project datasets.

The generator never invents natural-history prose. It creates a complete account
shell for every species and attaches authoritative research destinations so missing
fields can be filled from verifiable sources later.
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "field_guide_accounts.json"

COUNTRIES = {"Kenya": "KE", "Tanzania": "TZ", "Uganda": "UG", "Rwanda": "RW", "Burundi": "BI"}


def load(name, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def status(value):
    s = str(value or "").upper()
    for code, words in {"CR": ("CRITICALLY_ENDANGERED", "CR"), "EN": ("ENDANGERED", "EN"),
                        "VU": ("VULNERABLE", "VU"), "NT": ("NEAR_THREATENED", "NT"),
                        "LC": ("LEAST_CONCERN", "LC")}.items():
        if any(w in s for w in words):
            return code
    return None


def countries(values):
    found = set()
    def walk(value):
        if isinstance(value, (list, tuple, set)):
            for x in value: walk(x)
            return
        text = str(value or "").upper()
        for name, code in COUNTRIES.items():
            if name.upper() in text or f" {code} " in f" {text} ":
                found.add(code)
    for value in values: walk(value)
    return sorted(found)


def photos_for(record):
    if isinstance(record, list): return record
    if not isinstance(record, dict): return []
    result = []
    for category, items in record.items():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict): result.append({"category": category, **item})
    return result


def research_links(common, scientific):
    q = quote_plus(scientific or common or "")
    return {
        "avilist": f"https://avilist.org/checklist/explorer/?q={q}",
        "birdlife": f"https://datazone.birdlife.org/species/search?q={q}",
        "gbif": f"https://www.gbif.org/species/search?q={q}",
        "ebird": f"https://ebird.org/species/search?q={q}",
    }


def main():
    species = load("species.json", {}).get("species", [])
    details = load("species_details.json", {}).get("species", {})
    photos = load("photos.json", {}).get("species", {})
    accounts = {}

    for bird in species:
        bird_id = bird.get("id")
        if not bird_id: continue
        detail = details.get(bird_id, {})
        scientific = bird.get("scientific") or detail.get("matched_name")
        raw_distribution = detail.get("distribution", [])
        distribution = countries([bird.get("range"), bird.get("country"), bird.get("countries"),
                                  detail.get("country"), detail.get("countries"), raw_distribution])
        missing = ["identification", "similar_species", "voice", "habitat", "behaviour", "seasonal_movements"]
        accounts[bird_id] = {
            "id": bird_id, "name": bird.get("name"), "scientific_name": scientific,
            "order": bird.get("order"), "family": bird.get("family"), "genus": bird.get("genus"),
            "conservation_status": status(bird.get("status") or detail.get("conservation_status")),
            "east_africa": {"countries": distribution, "range_text": bird.get("range")},
            "identification": None, "similar_species": [], "voice": None, "habitat": None,
            "behaviour": None, "seasonal_movements": None, "plumages": [],
            "photos": photos_for(photos.get(bird_id, {})), "sources": detail.get("sources", []),
            "research_links": research_links(bird.get("name"), scientific),
            "data_status": {"account": "structured", "missing_prose": missing,
                            "natural_history_verified": False},
        }

    OUT.write_text(json.dumps({
        "version": 2, "scope": ["KE", "TZ", "UG", "RW", "BI"],
        "generated_by": "scripts/build_field_guide_accounts.py",
        "taxonomy_note": "Use AviList as the current consensus taxonomy; review source links before publishing prose.",
        "species": accounts,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(accounts)} field-guide accounts to {OUT}")

if __name__ == "__main__": main()
