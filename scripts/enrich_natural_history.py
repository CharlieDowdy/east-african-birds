"""Prepare a source-traceable natural-history enrichment queue.

This intentionally creates research records rather than inventing prose. Each species gets
source targets and explicit fields to verify. The website can safely show "not yet verified"
until a curator adds a sourced account.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "natural_history_queue.json"

FIELDS = ["identification", "similar_species", "voice", "habitat", "behaviour", "seasonal_movements"]
SOURCE_TARGETS = [
    {"provider": "AviList", "purpose": "taxonomy and range context", "url": "https://www.avilist.org/checklist/v2025b/"},
    {"provider": "BirdLife International", "purpose": "species account and conservation context", "url": "https://datazone.birdlife.org/"},
    {"provider": "eBird / Birds of the World", "purpose": "identification, habitat, behaviour and distribution research", "url": "https://birdsoftheworld.org/"},
    {"provider": "GBIF", "purpose": "occurrence evidence", "url": "https://www.gbif.org/"},
]

def load(name, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

def main():
    species = load("species.json", {}).get("species", [])
    accounts = load("field_guide_accounts.json", {}).get("species", {})
    queue = {}
    for bird in species:
        sid = bird.get("id")
        if not sid:
            continue
        account = accounts.get(sid, {})
        queue[sid] = {
            "id": sid,
            "name": bird.get("name"),
            "scientific_name": bird.get("scientific"),
            "priority": 1 if not account.get("identification") else 2,
            "fields_to_verify": [f for f in FIELDS if not account.get(f)],
            "source_targets": SOURCE_TARGETS,
            "status": "needs_curated_source",
            "editorial_rule": "Do not publish natural-history prose until a source and verification date are recorded.",
        }
    OUT.write_text(json.dumps({"version": 1, "generated_by": "scripts/enrich_natural_history.py", "species": queue}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(queue)} enrichment records")

if __name__ == "__main__":
    main()
