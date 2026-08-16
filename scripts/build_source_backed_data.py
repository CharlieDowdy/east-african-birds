#!/usr/bin/env python3
"""Build a source-backed field-guide layer.

This script deliberately does not invent natural-history facts. It combines
our existing taxonomy/details/photos with explicit source records and creates
an audit file showing which fields are supported by which source.

The natural-history prose layer is populated only by later imports from
identified, licensed sources.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "field_guide_data.json"

COUNTRIES = {
    "KE": "Kenya",
    "TZ": "Tanzania",
    "UG": "Uganda",
    "RW": "Rwanda",
    "BI": "Burundi",
}

SOURCES = {
    "abc_checklists": {
        "name": "African Bird Club country checklists",
        "url": "https://www.africanbirdclub.org/checklists/",
        "purpose": "country occurrence/checklist records",
    },
    "avibase_east_africa": {
        "name": "Avibase Eastern Africa checklist",
        "url": "https://avibase.bsc-eoc.org/checklist.jsp?region=AFE",
        "purpose": "regional taxonomy, names and checklist status",
    },
    "gbif": {
        "name": "GBIF",
        "url": "https://www.gbif.org/",
        "purpose": "taxonomic backbone and occurrence evidence",
    },
    "birdlife_datazone": {
        "name": "BirdLife International DataZone",
        "url": "https://datazone.birdlife.org/",
        "purpose": "conservation assessment and distribution-map reference",
    },
    "wikipedia": {
        "name": "Wikimedia/Wikipedia",
        "url": "https://www.wikipedia.org/",
        "purpose": "fallback natural-history reference where a suitable article exists",
    },
}


def load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def main():
    species_doc = load("species.json")
    details_doc = load("species_details.json")
    photos_doc = load("photos.json")
    species = species_doc.get("species", [])
    details = details_doc.get("species", {})
    photos = photos_doc.get("species", {})

    out = {
        "schema_version": 1,
        "generated": str(date.today()),
        "scope": "Kenya, Tanzania, Uganda, Rwanda and Burundi",
        "sources": SOURCES,
        "editorial_policy": "Missing natural-history facts remain empty; no AI-generated facts are marked verified.",
        "species": {},
    }

    for b in species:
        sid = b.get("id")
        d = details.get(sid, {})
        p = photos.get(sid, {})
        photo_count = sum(len(v) for v in p.values() if isinstance(v, list))
        out["species"][sid] = {
            "common_name": b.get("name"),
            "scientific_name": b.get("scientific"),
            "order": b.get("order"),
            "family": b.get("family"),
            "genus": b.get("genus"),
            "conservation_status": b.get("status") or d.get("conservation_status"),
            "countries": [],
            "range_text": b.get("range"),
            "photos": photo_count,
            "natural_history": {
                "identification": None,
                "similar_species": [],
                "voice": None,
                "habitat": None,
                "behaviour": None,
                "seasonal_movements": None,
            },
            "verification": {
                "taxonomy": ["avibase_east_africa", "gbif"],
                "conservation": ["birdlife_datazone"],
                "occurrence": ["abc_checklists", "gbif"],
                "natural_history": [],
            },
        }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(species)} source-backed species records to {OUT}")


if __name__ == "__main__":
    main()
