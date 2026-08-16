#!/usr/bin/env python3
"""Build source/provenance records from GBIF for the five-country field guide.

This script deliberately stores structured source metadata and links, not copied
natural-history prose. That keeps the repository auditable and avoids presenting
AI-generated text as factual bird content.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from urllib.parse import quote
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SPECIES = ROOT / "data/species.json"
OUT = ROOT / "data/source_records.json"
API = "https://api.gbif.org/v2/species/match?name="

COUNTRIES = {"KE":"Kenya","TZ":"Tanzania","UG":"Uganda","RW":"Rwanda","BI":"Burundi"}

def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent":"east-african-birds/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def main():
    raw = json.loads(SPECIES.read_text(encoding="utf-8"))
    birds = raw.get("species", raw if isinstance(raw, list) else [])
    records = {}
    for i, bird in enumerate(birds):
        scientific = bird.get("scientific") or bird.get("scientific_name") or bird.get("scientificName")
        if not scientific:
            continue
        try:
            m = get_json(API + quote(scientific, safe=""))
            usage = m.get("usage") or {}
            key = usage.get("key") or m.get("usageKey")
            rec = {
                "scientific_name_input": scientific,
                "gbif_taxon_key": key,
                "gbif_match_status": usage.get("status") or m.get("status"),
                "gbif_match_confidence": m.get("confidence"),
                "gbif_accepted_name": usage.get("name") or m.get("scientificName"),
                "gbif_rank": usage.get("rank") or m.get("rank"),
                "sources": [{
                    "provider": "GBIF Species API",
                    "url": f"https://www.gbif.org/species/{key}" if key else "https://www.gbif.org/species/search?q=" + quote(scientific),
                    "role": "taxonomic matching and source index"
                }],
                "country_sources": [
                    {"country_code": code, "country": name,
                     "provider": "African Bird Club",
                     "url": f"https://www.africanbirdclub.org/countries/{name.lower()}/{name.lower()}-introduction/"}
                    for code, name in COUNTRIES.items()
                ],
                "natural_history": {
                    "identification": {"status":"not_verified"},
                    "similar_species": {"status":"not_verified"},
                    "voice": {"status":"not_verified"},
                    "habitat": {"status":"not_verified"},
                    "behaviour": {"status":"not_verified"},
                    "seasonal_movements": {"status":"not_verified"}
                }
            }
            records[bird.get("id", scientific.lower().replace(" ", "-"))] = rec
        except Exception as exc:
            records[bird.get("id", scientific.lower().replace(" ", "-"))] = {
                "scientific_name_input": scientific,
                "sources": [],
                "error": str(exc),
                "natural_history": {"status":"not_verified"}
            }
        if i and i % 20 == 0:
            print(f"Processed {i}/{len(birds)}")
        time.sleep(0.05)
    payload = {
        "version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": list(COUNTRIES.values()),
        "policy": "Source metadata and links only; no AI-generated natural-history prose.",
        "species": records
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} source records to {OUT}")

if __name__ == "__main__":
    main()
